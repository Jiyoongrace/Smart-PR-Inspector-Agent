"""
LLM 프롬프트 템플릿 관리
모든 프롬프트를 중앙화하여 일관성 유지
"""

from string import Template


# ── 컨벤션 검증 프롬프트 ─────────────────────────────────────────────────

CONVENTION_CHECK_PROMPT = Template("""다음 코드 변경사항이 팀 컨벤션을 준수하는지 검사하세요.

컨벤션 규칙:
$rules

코드 Diff:
$diff

위반 사항을 JSON 배열로만 반환하세요 (설명 없이):
[{"file": "path.py", "line": 42, "rule": "규칙명", "message": "설명", "severity": "error|warning|info"}]

위반 없으면: []""")


# ── 테스트 생성 프롬프트 ─────────────────────────────────────────────────

TEST_GENERATION_PROMPT = Template("""당신은 Python 테스트 전문가입니다.
다음 함수들에 대한 pytest 테스트 코드를 작성하세요.

PR 제목: $pr_title
$issue_context

변경된 함수들:
$functions

코드 컨텍스트:
```
$diff_snippet
```

요구사항:
1. 각 함수에 대해 정상 케이스 2-3개
2. 예외/오류 케이스 1-2개
3. 경계값 테스트 1개
4. pytest.fixture 및 unittest.mock 적극 활용
5. 테스트명은 test_함수명_상황 패턴
6. 외부 의존성은 모두 mock 처리

실행 가능한 pytest 코드만 출력하세요:""")


# ── 테스트 수정 프롬프트 ─────────────────────────────────────────────────

TEST_FIX_PROMPT = Template("""다음 pytest 코드에서 오류가 발생했습니다. 수정된 코드를 반환하세요.

원본 코드:
```python
$test_code
```

에러 로그:
```
$error_log
```

재시도 횟수: $retry_count회

수정 지침:
- import 오류는 mock으로 처리
- 외부 의존성은 unittest.mock.patch 활용
- 타입 오류는 올바른 타입으로 수정
- 이전 시도와 다른 접근 방식 사용

실행 가능한 코드만 출력:""")


# ── 도메인 설명 프롬프트 ─────────────────────────────────────────────────

DOMAIN_EXPLANATION_PROMPT = Template("""다음 코드 변경이 비즈니스적으로 어떤 의미인지 200자 이내로 한국어로 설명하세요.

PR 제목: $pr_title

코드 변경:
$diff_snippet

$domain_context

응답 형식:
- 이 변경이 무엇을 하는지 (한 문장)
- 사용자/비즈니스에 미치는 영향 (한 문장)
- 주의사항 (있다면)

기술적 설명보다 비즈니스 관점으로 작성하세요.""")


# ── Swagger 업데이트 프롬프트 ─────────────────────────────────────────────

SWAGGER_UPDATE_PROMPT = Template("""다음 API 변경사항에 대한 OpenAPI/Swagger 문서 업데이트 초안을 YAML로 작성하세요.

변경된 엔드포인트:
$api_changes

필요한 업데이트:
$updates

간결하게 핵심만 작성하고 실제 Swagger 경로 정의 형식으로 출력하세요:""")


# ── 최종 리뷰 코멘트 프롬프트 ─────────────────────────────────────────────

REVIEW_SUMMARY_PROMPT = Template("""다음 분석 결과를 바탕으로 간결한 PR 리뷰 요약을 한국어로 작성하세요.

컨벤션 결과: $convention_summary
테스트 결과: $test_summary
영향도: $impact_summary
도메인 설명: $domain_explanation

전체적인 머지 가능 여부와 주요 액션 아이템을 2-3문장으로 요약하세요:""")


# ── PR 자동 생성 프롬프트 ─────────────────────────────────────────────────

PR_CREATION_PROMPT = Template("""당신은 GitHub PR 작성 전문가입니다.
아래 커밋 목록을 분석하여 명확하고 유용한 PR 제목과 본문을 한국어로 작성하세요.

레포지토리: $repo
병합 방향: $head → $base
커밋 수: $commit_count개

커밋 목록:
$commits

출력 형식을 정확히 지켜주세요:

TITLE: (feat/fix/refactor/docs/chore 중 하나로 시작하는 간결한 제목, 60자 이내)
BODY:
## 변경 사항
(커밋들을 분석하여 주요 변경 내용을 bullet point로 요약)

## 변경 이유
(이 변경이 왜 필요한지 추론하여 1-2문장으로 작성)

## 테스트 방법
(리뷰어가 확인해야 할 사항을 간략히 작성)

## 체크리스트
- [ ] 코드 리뷰 완료
- [ ] 테스트 통과 확인
- [ ] 문서 업데이트 (해당 시)""")


# ── 버그 재현 테스트 프롬프트 ─────────────────────────────────────────────

BUG_REPRODUCTION_PROMPT = Template("""다음 GitHub 이슈를 재현하는 pytest 테스트를 작성하세요.

이슈 제목: $issue_title
이슈 내용: $issue_body

관련 코드:
$related_code

요구사항:
1. 버그를 재현하는 테스트 (수정 전에는 FAIL, 수정 후에는 PASS해야 함)
2. 이슈 번호와 제목을 docstring에 포함
3. 명확한 assert 메시지

pytest 코드만 출력:""")
