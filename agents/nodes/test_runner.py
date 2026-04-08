"""
테스트 실행 노드
Docker 격리 환경에서 pytest 실행 + 재시도 로직
"""

import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from agents.state import AgentState, NodeStatus, TestResult

logger = logging.getLogger(__name__)

MAX_RETRY = 1  # 재시도 1회로 제한 (속도 우선)
TIMEOUT_SECONDS = 30  # 30초 (Docker pull 대기 제거)


def test_runner_node(state: AgentState) -> AgentState:
    """pytest를 Docker 또는 로컬 환경에서 실행"""
    state.node_status.test_run = NodeStatus.RUNNING

    if not state.test_result or not state.test_result.test_code:
        state.node_status.test_run = NodeStatus.SKIPPED
        return state

    # 테스트 파일 저장
    test_file = _save_temp_test(state.test_result.test_code)

    start_time = time.time()

    # 로컬 실행 우선 (Docker는 초기 이미지 pull로 느림)
    # ENABLE_DOCKER_TESTS=true 환경변수로 명시 활성화 가능
    use_docker = os.getenv("ENABLE_DOCKER_TESTS", "false").lower() == "true" and _check_docker_available()

    if use_docker:
        result = _run_with_docker(test_file)
    else:
        result = _run_locally(test_file)

    duration = time.time() - start_time
    result.duration_seconds = round(duration, 2)
    result.retry_count = state.test_result.retry_count
    result.test_code = state.test_result.test_code

    state.test_result = result
    state.node_status.test_run = NodeStatus.SUCCESS if result.passed else NodeStatus.FAILED

    logger.info(
        f"테스트 실행 완료: {'통과' if result.passed else '실패'} "
        f"({result.passed_tests}/{result.total_tests}, {duration:.1f}초)"
    )
    return state


def fix_test_code_node(state: AgentState) -> AgentState:
    """테스트 실패 시 LLM으로 코드 수정 후 재시도"""
    if not state.test_result:
        return state

    retry_count = state.test_result.retry_count + 1
    logger.info(f"테스트 코드 수정 중 (재시도 {retry_count}/{MAX_RETRY})")

    fixed_code = _fix_with_llm(
        test_code=state.test_result.test_code,
        error_log=state.test_result.stderr,
        retry_count=retry_count,
    )

    state.test_result = TestResult(
        passed=False,
        test_code=fixed_code,
        retry_count=retry_count,
    )
    return state


def should_retry(state: AgentState) -> str:
    """재시도 여부 결정 함수 (LangGraph conditional edge용)"""
    if not state.test_result:
        return "fail"
    if state.test_result.passed:
        return "success"
    if state.test_result.retry_count < MAX_RETRY:
        return "retry"
    return "fail"


def _save_temp_test(test_code: str) -> str:
    test_dir = Path(tempfile.gettempdir()) / "pr_inspector_tests"
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / "test_generated.py"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_code)
    return str(test_file)


def _check_docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _run_with_docker(test_file: str) -> TestResult:
    """Docker 컨테이너에서 격리 실행"""
    try:
        import docker

        client = docker.from_env()
        test_dir = str(Path(test_file).parent)

        container = client.containers.run(
            image="python:3.11-slim",
            command=f"bash -c 'pip install pytest pytest-timeout -q && pytest /tests/test_generated.py -v --tb=short --timeout=60'",
            volumes={
                test_dir: {"bind": "/tests", "mode": "rw"}
            },
            detach=True,
            mem_limit="256m",
            cpu_period=100000,
            cpu_quota=50000,  # 50% CPU
        )

        exit_code = container.wait(timeout=TIMEOUT_SECONDS)
        logs = container.logs().decode("utf-8", errors="replace")
        container.remove(force=True)

        passed = exit_code["StatusCode"] == 0
        stats = _parse_pytest_output(logs)

        return TestResult(
            passed=passed,
            stdout=logs if passed else "",
            stderr=logs if not passed else "",
            total_tests=stats["total"],
            passed_tests=stats["passed"],
            failed_tests=stats["failed"],
        )

    except Exception as e:
        logger.warning(f"Docker 실행 실패, 로컬로 폴백: {e}")
        return _run_locally(test_file)


def _run_locally(test_file: str) -> TestResult:
    """로컬 환경에서 pytest 실행"""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", test_file, "-v", "--tb=short", "--timeout=60"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )

        passed = result.returncode == 0
        output = result.stdout + result.stderr
        stats = _parse_pytest_output(output)

        return TestResult(
            passed=passed,
            stdout=result.stdout,
            stderr=result.stderr,
            total_tests=stats["total"],
            passed_tests=stats["passed"],
            failed_tests=stats["failed"],
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            passed=False,
            stderr=f"테스트 타임아웃: {TIMEOUT_SECONDS}초 초과",
        )
    except Exception as e:
        return TestResult(
            passed=False,
            stderr=str(e),
        )


def _parse_pytest_output(output: str) -> dict:
    """pytest 출력에서 통계 추출"""
    stats = {"total": 0, "passed": 0, "failed": 0}

    # "3 passed, 1 failed" 패턴
    match = re.search(r"(\d+) passed", output)
    if match:
        stats["passed"] = int(match.group(1))

    match = re.search(r"(\d+) failed", output)
    if match:
        stats["failed"] = int(match.group(1))

    stats["total"] = stats["passed"] + stats["failed"]

    # "5 passed" 단독 패턴
    match = re.search(r"(\d+) passed", output)
    if match and stats["total"] == 0:
        stats["passed"] = int(match.group(1))
        stats["total"] = stats["passed"]

    return stats


def _fix_with_llm(test_code: str, error_log: str, retry_count: int) -> str:
    """LLM으로 실패한 테스트 코드 수정"""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        prompt = f"""다음 pytest 코드에서 에러가 발생했습니다. 수정된 코드를 반환하세요.

원본 테스트 코드:
```python
{test_code[:2000]}
```

에러 로그:
```
{error_log[:1000]}
```

지침:
- import 오류는 mock으로 처리
- 외부 의존성은 pytest.fixture + unittest.mock 활용
- 실행 가능한 코드만 출력 (마크다운 없이)
- 재시도 {retry_count}회차이므로 이전과 다른 접근 방식 시도"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        code_match = re.search(r"```python\n([\s\S]+?)\n```", raw)
        return code_match.group(1) if code_match else raw.strip()

    except Exception as e:
        logger.error(f"LLM 코드 수정 실패: {e}")
        return test_code  # 원본 반환
