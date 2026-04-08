# Pain Point 분석 및 Task 분해

## 1단계: Pain Points 식별

| Pain | 구체적 문제 | 빈도 | 영향도 |
|------|------------|------|--------|
| 리뷰 병목 | 시니어 1명이 하루 10+ PR 리뷰 | 매일 | 높음 |
| 컨벤션 위반 | 네이밍, 들여쓰기 등 반복 지적 | PR당 3회 | 중간 |
| 사이드 이펙트 | 타 모듈 영향도 파악 안됨 | 월 5회 | 치명적 |
| 문서 불일치 | API 변경 후 Swagger 미업데이트 | 월 8회 | 높음 |
| 도메인 이해 부족 | 비즈니스 로직 변경 설명 부재 | PR당 1회 | 중간 |

---

## 2단계: Task → Skill → Tool 분해

### Sub-task 1: 코드 변경 수집
- **입력**: PR Number, Repository
- **출력**: Diff 파일, 변경된 파일 목록
- **Skill**: GitHub API 호출, Diff 파싱
- **Tool**: PyGithub, unidiff

### Sub-task 2: 컨벤션 검증
- **입력**: Diff 파일, 룰북 문서
- **출력**: 위반 항목 리스트
- **Skill**: AST 분석, 규칙 매칭
- **Tool**: ast 모듈, pylint, LLM (Claude/GPT-4)

### Sub-task 3: 테스트 계획 생성
- **입력**: 변경된 함수/클래스, 기존 테스트 코드
- **출력**: 테스트 스크립트 (.py)
- **Skill**: 코드 문맥 이해, 테스트 템플릿 생성
- **Tool**: LLM (Claude), Jinja2

### Sub-task 4: 테스트 실행
- **입력**: 테스트 스크립트
- **출력**: Pass/Fail, 에러 로그
- **Skill**: 샌드박스 실행, 타임아웃 관리
- **Tool**: pytest, Docker (격리 환경)

### Sub-task 5: 영향도 분석
- **입력**: 변경 함수 시그니처, 호출 그래프
- **출력**: 영향받는 모듈 리스트
- **Skill**: 정적 분석, 의존성 추적
- **Tool**: ast, LLM

### Sub-task 6: 도메인 설명 생성
- **입력**: 변경 내역, 도메인 문서 (RAG)
- **출력**: 비즈니스 영향도 자연어 설명
- **Skill**: 벡터 검색, 문맥 합성
- **Tool**: ChromaDB, LangChain

### Sub-task 7: 문서 동기화 검사
- **입력**: API 변경 내역, 기존 Swagger/README
- **출력**: 업데이트 초안 (Markdown/YAML)
- **Skill**: Diff 비교, 템플릿 기반 생성
- **Tool**: pydantic, swagger-parser, LLM

### Sub-task 8: 리뷰 코멘트 작성
- **입력**: 전체 검증 결과
- **출력**: GitHub PR Comment (Markdown)
- **Skill**: 구조화된 리포트 생성
- **Tool**: GitHub API, Slack API

---

## 3단계: 우선순위 매트릭스

| Task | 구현 난이도 | 비즈니스 가치 | 우선순위 |
|------|------------|--------------|---------|
| 코드 변경 수집 | 낮음 | 필수 | P0 |
| 컨벤션 검증 | 중간 | 높음 | P0 |
| 리뷰 코멘트 | 낮음 | 필수 | P0 |
| 테스트 생성 | 높음 | 높음 | P1 |
| 영향도 분석 | 중간 | 높음 | P1 |
| 문서 동기화 | 중간 | 중간 | P2 |
| 도메인 설명 | 높음 | 높음 | P2 |
| Slack 연동 | 중간 | 중간 | P2 |
| 메모리 학습 | 높음 | 중간 | P3 |
