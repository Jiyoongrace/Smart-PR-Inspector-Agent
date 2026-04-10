# SKILL.md — Smart PR Inspector Agent 스킬 정의

> 이 파일은 에이전트가 수행할 수 있는 스킬을 선언적으로 정의합니다.
> `config/skills.py`에서 파싱되어 오케스트레이터와 각 노드에서 활용됩니다.

---

## skills

### pr_data_collection
- id: fetch
- description: GitHub PR 데이터 수집 (diff, 메타데이터, 변경 파일 목록)
- trigger: PR 번호 + 레포지토리 입력
- tools: [PyGithub, unidiff, GitHub REST API]
- input: pr_number, repo
- output: PRData (diff, changed_files, author, title, labels, linked_issues)
- model: none
- timeout: 30s

### convention_check
- id: convention
- description: AST 정적분석 + LLM 하이브리드 컨벤션 위반 검사
- trigger: diff 존재
- tools: [ast, yaml, LLM]
- input: diff, changed_files
- output: ConventionResult (violations list, passed, summary)
- model: fast
- prompt: CONVENTION_CHECK_PROMPT
- parallel_group: analysis_fork

### bdd_scenario_generation
- id: test_gen
- description: BDD 형식(Given/When/Then) 테스트 시나리오 AI 생성
- trigger: diff 존재
- tools: [LLM]
- input: diff, pr_title, pr_body, linked_issues
- output: TestResult (scenarios list)
- model: smart
- prompt: SCENARIO_GENERATION_PROMPT
- parallel_group: analysis_fork

### architecture_review
- id: arch_review
- description: 아키텍처 룰 위반 탐지 + HITL 시니어 승인 대기
- trigger: convention + test_gen 완료 (Join 후)
- tools: [ast, regex, Slack SDK]
- input: diff, changed_files
- output: ArchReviewResult (violations, approval_status)
- model: none
- hitl: true
- hitl_actions: [approved, rejected]
- checks: [layer_violation, hardcoded_secret, god_class, circular_import]

### scenario_evaluation
- id: test_run
- description: AI 시나리오를 코드 diff와 교차 검증하여 통과/실패 판정
- trigger: arch_review 승인
- tools: [LLM, Docker]
- input: scenarios, diff
- output: TestResult (verdict, reasoning, confidence per scenario)
- model: smart
- prompt: SCENARIO_EVALUATION_PROMPT
- retry: true
- max_retries: 3
- retry_node: fix_test

### test_fix
- id: fix_test
- description: 테스트 실패 시 LLM으로 코드 자동 수정
- trigger: test_run 실패 + retry_count < 3
- tools: [LLM]
- input: test_code, error_log, retry_count
- output: 수정된 test_code
- model: smart
- prompt: TEST_FIX_PROMPT

### impact_analysis
- id: impact
- description: AST 호출그래프 정적분석 + LLM 비즈니스 영향도 분석
- trigger: test_run 완료 (성공/실패 무관)
- tools: [ast, LLM]
- input: diff, changed_files
- output: ImpactAnalysis (risk_level, affected_modules, business_impact)
- model: fast
- prompt: BUSINESS_IMPACT_PROMPT

### domain_explanation
- id: domain_explain
- description: Hybrid RAG (Dense+Sparse+Re-ranking)으로 도메인 문서 검색 후 비즈니스 설명 생성
- trigger: impact 완료
- tools: [ChromaDB, BM25, CrossEncoder, LLM]
- input: pr_title, diff_snippet, impact_analysis
- output: domain_explanation (200자), domain_sources
- model: fast
- prompt: DOMAIN_EXPLANATION_PROMPT
- rag:
  - dense: ChromaDB (DefaultEmbeddingFunction)
  - sparse: BM25Okapi (rank-bm25)
  - fusion: Reciprocal Rank Fusion (k=60)
  - reranker: cross-encoder/ms-marco-MiniLM-L-6-v2
  - top_k: 5

### doc_sync_check
- id: doc_sync
- description: API 엔드포인트 변경 감지 및 Swagger 업데이트 초안 생성
- trigger: domain_explain 완료
- tools: [regex, LLM]
- input: diff, has_api_changes
- output: doc_updates (Swagger YAML 초안)
- model: fast
- prompt: SWAGGER_UPDATE_PROMPT
- skip_condition: API 파일 변경 없음

### review_comment
- id: comment
- description: 전체 분석 결과를 통합한 GitHub PR 코멘트 마크다운 생성 및 게시
- trigger: doc_sync 완료
- tools: [PyGithub]
- input: convention_result, test_result, impact_analysis, domain_explanation, doc_updates
- output: final_comment (GitHub PR에 게시)
- model: none

### slack_notification
- id: slack
- description: Slack Block Kit 인터랙티브 메시지 전송 (Approve/Request Changes 버튼)
- trigger: comment 완료
- tools: [slack_sdk, Incoming Webhook]
- input: 전체 분석 결과
- output: slack_thread_id
- model: none
- actions: [approve_pr, request_changes, view_pr]

---

## workflow

### execution_order
- entry: fetch
- parallel: [convention, test_gen]
- join_then: arch_review
- conditional:
  - node: arch_review
    routing: check_arch_approval
    edges:
      approved: test_run
      rejected: comment
- conditional:
  - node: test_run
    routing: should_retry
    edges:
      retry: fix_test
      success: impact
      fail: impact
- sequence: [impact, domain_explain, doc_sync, comment, slack]
- end: slack

### models
- fast: gpt-4o-mini
- smart: gpt-4o-mini
