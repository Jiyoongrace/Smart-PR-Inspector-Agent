# CLAUDE.md — Smart PR Inspector Agent

Claude Code가 이 프로젝트에서 작업할 때 참고하는 지침입니다.

## 프로젝트 개요

- **목적**: GitHub PR 자동 분석 AI Agent 플랫폼
- **핵심 기술**: LangGraph + Anthropic Claude + FastAPI + Next.js
- **주요 언어**: Python (백엔드), TypeScript (프론트엔드)

## 코드 규칙

### Python
- 모든 함수에 타입 힌트 필수
- 한국어 docstring 작성
- `logging` 모듈 사용 (print 금지)
- Pydantic v2 BaseModel로 데이터 검증
- 예외 처리: 구체적인 Exception 클래스 지정

### TypeScript / React
- `"use client"` 지시어 필요한 컴포넌트만 표시
- Props 타입은 별도 interface로 정의
- Zustand store 접근은 `useAppStore()` 훅 사용
- Tailwind CSS + `cn()` 유틸리티로 스타일링

### 파일 구조 규칙
- Agent 노드는 반드시 `agents/nodes/` 에 추가
- 새 노드 추가 시 `agents/nodes/__init__.py`에 export 추가
- LangGraph 엣지는 `agents/orchestrator.py`에서만 수정
- 프롬프트 문자열은 `config/prompts.py`에 중앙화

## 환경변수

필수값:
- `ANTHROPIC_API_KEY`: Claude API 키 (sk-ant-...)
- `GITHUB_TOKEN`: GitHub PAT (repo, pull_requests 권한)

선택값:
- `SLACK_BOT_TOKEN`: Slack 알림 사용 시
- `REDIS_URL`: 캐싱 (기본값: redis://localhost:6379)
- `CHROMA_HOST`: 벡터 DB (기본값: localhost)

## 개발 시 주의사항

1. **LangGraph StateGraph**: `AgentState`는 불변성 유지, 각 노드는 새 state 반환
2. **LLM 호출**: 항상 `try/except`로 감싸고 fallback 처리
3. **Docker 의존성**: `docker` 패키지 없을 시 로컬 실행으로 폴백
4. **SSE 스트리밍**: `yield` 기반 비동기 제너레이터 사용
5. **Rate Limiting**: GitHub API는 5000 req/hour 제한 주의

## 로컬 개발 실행

```bash
# 인프라만 Docker로 실행
docker-compose up -d redis chromadb

# 백엔드 개발 모드
uvicorn api.webhook:app --reload --port 8000

# 프론트엔드 개발 모드
cd frontend && npm run dev
```

## 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 특정 노드 테스트
pytest tests/test_convention.py -v

# 커버리지
pytest tests/ --cov=agents --cov-report=html
```

## 버전 관리

변경사항은 `CHANGES.md`에 기록합니다.
형식: `## v{버전} — {날짜}\n- {변경 내용}`

## 주의: 보안

- `.env` 파일을 절대 커밋하지 마세요
- API 키는 항상 환경변수로 관리
- GitHub Webhook 서명은 반드시 검증
- Docker 실행 시 메모리/CPU 제한 적용
