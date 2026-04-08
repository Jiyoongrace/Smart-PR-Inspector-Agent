# 구현 가이드

## Phase 1: 기본 워크플로우 구축 (Week 1-2)

### 1.1 환경 설정

```bash
# 가상환경 생성
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력
```

### 1.2 State 모델 (`agents/state.py`)
- Pydantic BaseModel 기반 AgentState 정의
- PR 데이터, 컨벤션 결과, 테스트 결과, 영향도, 코멘트 포함

### 1.3 LangGraph 워크플로우 (`agents/orchestrator.py`)
- StateGraph 생성 및 노드 등록
- Conditional Edge로 재시도 로직 구현
- Parallel Fork: convention_check + test_gen 동시 실행

---

## Phase 2: 각 Node 구현 (Week 3-4)

### 2.1 GitHub 데이터 수집 (`agents/nodes/fetcher.py`)
- PyGithub로 PR diff, 파일 목록, 메타데이터 수집
- `unidiff`로 변경 라인 파싱

### 2.2 컨벤션 체크 (`agents/nodes/convention.py`)
- AST 기반: snake_case, 타입 힌트, 매직넘버 체크
- LLM 보조: 복잡한 패턴, 가독성 분석
- `config/conventions.yaml` 룰북 연동

### 2.3 테스트 생성 (`agents/nodes/test_gen.py`)
- Claude로 pytest 코드 생성
- 정상 케이스 3개 + 예외 케이스 2개 + 경계값 1개
- Jinja2 템플릿 활용

### 2.4 테스트 실행 (`agents/nodes/test_runner.py`)
- Docker SDK로 격리 환경에서 pytest 실행
- 5분 타임아웃, 최대 3회 재시도
- 실패 시 에러 로그 → LLM 수정 → 재실행

### 2.5 영향도 분석 (`agents/nodes/impact.py`)
- AST로 전체 프로젝트 호출 그래프 생성
- DFS로 변경 함수의 의존성 추적

---

## Phase 3: 고급 기능 구현 (Week 5-6)

### 3.1 RAG 도메인 설명 (`agents/nodes/domain_explainer.py`)
- ChromaDB에 도메인 문서 벡터화 저장
- 변경 코드 기반 유사 문서 검색
- 비즈니스 영향도 300자 설명 생성

### 3.2 Swagger 동기화 (`agents/nodes/doc_sync.py`)
- FastAPI 데코레이터 AST 파싱
- 기존 OpenAPI 스펙과 diff 비교
- 업데이트 초안 자동 생성

### 3.3 GitHub 코멘트 (`agents/nodes/commenter.py`)
- 전체 분석 결과를 Markdown 리포트로 구조화
- GitHub API로 PR에 코멘트 게시

---

## Phase 4: Slack 연동 (Week 7)

### 4.1 Slack 알림 (`agents/nodes/slack_notify.py`)
- Block Kit으로 인터랙티브 메시지 구성
- 승인/거부 버튼 클릭 → GitHub Review 자동 제출

### 4.2 Webhook 서버 (`api/webhook.py`)
- FastAPI로 GitHub Webhook 수신
- Slack Interactive Events 처리

---

## Phase 5: 프론트엔드 UI (Week 8-9)

### 5.1 레이아웃
- 좌측 사이드바: PR 목록, 네비게이션
- 상단 헤더: 레포지토리 선택, 상태 표시
- 중앙 워크스페이스: 분석 결과, 워크플로우 시각화
- 우측 채팅 패널: Agent와 대화

### 5.2 실시간 업데이트
- SSE로 Agent 실행 상태 스트리밍
- 워크플로우 노드별 진행 상태 시각화

---

## 로컬 개발 실행

```bash
# Docker Compose로 전체 스택 시작
docker-compose up -d

# API 서버 (개발 모드)
uvicorn api.webhook:app --reload --port 8000

# 프론트엔드
cd frontend && npm run dev

# ngrok으로 GitHub Webhook 테스트
ngrok http 8000
```

---

## 테스트

```bash
# 단위 테스트
pytest tests/ -v

# 특정 노드 테스트
pytest tests/test_convention.py -v

# 커버리지
pytest tests/ --cov=agents --cov-report=html
```
