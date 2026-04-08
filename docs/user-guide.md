# 📖 Smart PR Inspector — 사용자 가이드

> AI Agent가 GitHub PR을 자동으로 분석해주는 플랫폼입니다.
> 이 가이드에서는 플랫폼을 처음 사용하는 분도 쉽게 따라할 수 있도록 설명합니다.

---

## 목차

1. [처음 시작하기 (환경 설정)](#1-처음-시작하기-환경-설정)
2. [화면 구성 이해하기](#2-화면-구성-이해하기)
3. [PR 분석 실행하기](#3-pr-분석-실행하기)
4. [Agent 워크플로우 읽는 법](#4-agent-워크플로우-읽는-법)
5. [분석 결과 탭 가이드](#5-분석-결과-탭-가이드)
6. [Agent Chat 활용하기](#6-agent-chat-활용하기)
7. [Slack 연동으로 PR 승인하기](#7-slack-연동으로-pr-승인하기)
8. [도메인 문서 등록하기 (RAG)](#8-도메인-문서-등록하기-rag)
9. [컨벤션 룰 커스터마이징](#9-컨벤션-룰-커스터마이징)
10. [자주 묻는 질문 (FAQ)](#10-자주-묻는-질문-faq)

---

## 1. 처음 시작하기 (환경 설정)

### 1단계 — 필수 API 키 준비

| 키 | 발급 위치 | 용도 |
|----|-----------|------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | PR 분석 AI (필수) |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → Personal access tokens | PR 데이터 읽기 (필수) |
| `SLACK_BOT_TOKEN` | [api.slack.com](https://api.slack.com/apps) | Slack 알림 (선택) |

> **GitHub Token 권한**: `repo` (전체) 또는 최소 `pull_requests: Read`, `contents: Read` 권한 필요

### 2단계 — 환경변수 설정

프로젝트 루트에 `.env` 파일을 열고 아래 값을 입력합니다.

```bash
# 필수
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...

# 선택 (Slack 알림 사용 시)
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#code-review
```

### 3단계 — 실행

```bash
# 방법 A: Docker Compose (추천 — 모든 서비스 한 번에)
docker-compose up -d

# 방법 B: 개별 실행 (개발 모드)
uvicorn api.webhook:app --reload --port 8000   # 백엔드 터미널 1
cd frontend && npm install && npm run dev       # 프론트엔드 터미널 2
```

### 4단계 — 브라우저 열기

```
http://localhost:3000
```

---

## 2. 화면 구성 이해하기

```
┌─────────────────────────────────────────────────────────────────┐
│                        ① 상단 헤더                              │
│  [≡] [레포지토리 입력] [PR 번호] [▶ 분석 시작]   [🔔] [💬]    │
├──────────┬──────────────────────────────────────┬───────────────┤
│          │         ③ 중앙 워크스페이스           │               │
│ ② 사이   │  ┌──────────────┬──────────────────┐ │  ④ Agent      │
│  드바     │  │ Agent 워크   │   분석 결과       │ │   Chat        │
│          │  │ 플로우        │   (탭별 상세)     │ │               │
│  PR 목록  │  │  노드별 상태  │                  │ │  Claude AI    │
│  검색     │  │  실시간 표시  │                  │ │  대화 공간    │
│  네비     │  └──────────────┴──────────────────┘ │               │
└──────────┴──────────────────────────────────────┴───────────────┘
```

| 영역 | 역할 |
|------|------|
| **① 상단 헤더** | PR 분석 입력창, 실행 버튼, 패널 토글 |
| **② 좌측 사이드바** | 분석된 PR 목록, 검색, 상태 확인 |
| **③ 중앙 워크스페이스** | Agent 실행 흐름 + 분석 결과 상세 |
| **④ 우측 채팅** | Claude AI와 PR에 대해 자유롭게 대화 |

### 패널 토글 방법

- **사이드바 열기/닫기**: 헤더 좌측 `☰` 버튼
- **채팅 패널 열기/닫기**: 헤더 우측 `💬` 버튼

---

## 3. PR 분석 실행하기

### 방법 A — 헤더에서 직접 입력

1. 상단 헤더에서 레포지토리 입력란에 `owner/repo` 형식으로 입력
   ```
   예시: acme-corp/backend-api
   ```
2. PR 번호 입력란에 숫자 입력
   ```
   예시: 1234
   ```
3. `▶ 분석 시작` 버튼 클릭 (또는 Enter 키)
4. 중앙 워크플로우에서 각 노드가 실시간으로 실행되는 것을 확인

### 방법 B — GitHub Webhook 자동 트리거

PR이 생성될 때 자동으로 분석이 시작되도록 설정할 수 있습니다.

```bash
# 1. ngrok으로 외부 URL 생성 (로컬 개발 시)
ngrok http 8000
# → https://abc123.ngrok.io 같은 URL이 생성됨

# 2. GitHub 레포 → Settings → Webhooks → Add webhook
#    Payload URL: https://abc123.ngrok.io/webhook/github
#    Content type: application/json
#    Events: Pull requests
```

이후 PR을 열거나 업데이트하면 자동으로 분석이 시작되고 결과가 UI에 표시됩니다.

### 방법 C — API 직접 호출

```bash
curl -X POST "http://localhost:8000/api/analyze?pr_number=1234&repo=owner/repo"
```

---

## 4. Agent 워크플로우 읽는 법

중앙 왼쪽 패널에서 Agent의 실행 흐름을 실시간으로 확인할 수 있습니다.

### 노드 상태 표시

| 아이콘 | 상태 | 의미 |
|--------|------|------|
| `—` 회색 | **대기 중 (Pending)** | 아직 실행 전 |
| `⟳` 파란색 (회전) | **실행 중 (Running)** | 현재 처리 중 |
| `✓` 초록색 | **완료 (Success)** | 정상 완료 |
| `✗` 빨간색 | **실패 (Failed)** | 오류 발생 |
| `—` 진회색 | **스킵 (Skipped)** | 조건 미충족으로 건너뜀 |

### 워크플로우 순서

```
PR 수집 → [컨벤션 검사 + 테스트 생성 (병렬)] → 테스트 실행
       → 영향도 분석 → 도메인 설명 → 문서 동기화
       → GitHub 코멘트 → Slack 알림
```

> **병렬 실행**: `컨벤션 검사`와 `테스트 생성`은 동시에 실행됩니다.
> **재시도**: 테스트가 실패하면 AI가 코드를 수정해 최대 3회 재시도합니다.

---

## 5. 분석 결과 탭 가이드

중앙 오른쪽 패널의 탭을 클릭해 각 분석 결과를 확인합니다.

### 📌 개요 탭

가장 먼저 보게 되는 탭입니다. 다음 내용을 확인할 수 있습니다.

- **PR 기본 정보**: 제목, 작성자, 브랜치, 변경 파일 수
- **요약 카드 4개**: 컨벤션 / 테스트 / 리스크 / 문서 상태
- **비즈니스 영향도**: AI가 도메인 문서를 참고해 설명한 내용
- **GitHub 코멘트 미리보기**: 실제 PR에 게시될 코멘트 내용

### 📋 컨벤션 탭

코딩 규칙 위반 사항을 파일별로 확인합니다.

- **빨간 테두리**: 오류 (Error) — 반드시 수정 필요
- **노란 테두리**: 경고 (Warning) — 수정 권장
- **파란 테두리**: 정보 (Info) — 참고사항

파일 이름을 클릭하면 위반 목록이 펼쳐집니다.

```
예시:
📂 src/order_service.py (3건)
  🔴 Line 42: 함수명 `getData` → snake_case 필요
  🟡 Line 58: 매직넘버 `7` → 상수로 분리 권장
  🔵 Line 103: 반환 타입 힌트 누락
```

### 🧪 테스트 탭

AI가 자동 생성하고 실행한 테스트 결과입니다.

- **전체/통과/실패** 통계 숫자 확인
- **오류 로그**: 실패 시 펼쳐서 확인 가능
- **생성된 테스트 코드**: AI가 작성한 pytest 코드 전체 보기

> 테스트가 실패해도 AI가 자동으로 코드를 수정하며 최대 3회 재시도합니다.
> 재시도 횟수는 결과 패널에서 확인할 수 있습니다.

### 🔗 영향도 탭

변경된 코드가 다른 부분에 미치는 영향을 확인합니다.

- **리스크 레벨**: 🟢 낮음 / 🟡 보통 / 🟠 높음 / 🔴 위험
- **변경된 함수 목록**: 이번 PR에서 수정된 함수들
- **영향받는 모듈**: 변경된 함수를 호출하는 파일과 라인 번호
- **API 변경 경고**: FastAPI 엔드포인트 변경 감지 시 표시

### 📄 문서 탭

Swagger/OpenAPI 문서 업데이트가 필요한 경우 표시됩니다.

- API 변경이 없으면 "문서 동기화 완료" 표시
- 변경이 있으면 AI가 제안한 Swagger YAML 초안 표시

---

## 6. Agent Chat 활용하기

우측 채팅 패널에서 Claude AI와 대화하며 분석 결과를 더 깊이 이해할 수 있습니다.

### 채팅 열기

헤더 우측 `💬` 버튼을 클릭하거나, 처음부터 열려 있습니다.

### 유용한 질문 예시

**분석 결과 이해하기**
```
컨벤션 위반 항목들을 하나씩 설명해줘
테스트가 왜 실패했는지 분석해줘
리스크가 높음으로 나온 이유가 뭐야?
```

**수정 방향 물어보기**
```
Line 42의 위반 사항을 어떻게 고치면 돼?
영향받는 모듈들을 어떻게 처리해야 해?
이 PR을 머지해도 안전해?
```

**빠른 질문 버튼**

채팅창 첫 화면에 자주 묻는 질문 버튼이 있습니다:
- `컨벤션 위반 설명해줘`
- `테스트 실패 원인은?`
- `영향도 요약해줘`
- `머지해도 괜찮아?`

버튼을 클릭하면 입력창에 자동 입력됩니다.

### 단축키

- `Enter` — 메시지 전송
- `Shift + Enter` — 줄바꿈

---

## 7. Slack 연동으로 PR 승인하기

Slack을 연동하면 분석 완료 후 Slack으로 알림이 오고, Slack에서 바로 승인/거부할 수 있습니다.

### 설정 방법

1. `.env`에 Slack 토큰 추가
   ```bash
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_SIGNING_SECRET=...
   SLACK_CHANNEL=#code-review
   ```

2. Slack App에서 Interactivity 활성화
   ```
   Slack API → 앱 선택 → Interactivity & Shortcuts
   Request URL: https://your-domain.com/slack/events
   ```

### Slack 메시지 예시

```
🤖 Smart PR Inspector 분석 완료

PR #1234: 재고 차감 로직 개선
작성자: jiyoon | main ← feature/discount

✅ 컨벤션: 통과
✅ 테스트: 5/5 통과
🟡 리스크: MEDIUM (3개 모듈 영향)
⚠️ API 변경: 감지됨

📖 비즈니스 영향도:
이번 변경은 VIP 고객 할인 정책을 수정합니다...

[✅ 승인]  [🔄 수정 요청]  [📋 상세 보기]
```

### 버튼 동작

| 버튼 | 동작 |
|------|------|
| **✅ 승인** | GitHub PR에 Approve Review 자동 제출 |
| **🔄 수정 요청** | GitHub PR에 Request Changes Review 제출 |
| **📋 상세 보기** | GitHub PR 페이지로 이동 |

---

## 8. 도메인 문서 등록하기 (RAG)

팀의 내부 문서(비즈니스 로직, 정책 문서 등)를 등록하면 AI가 PR 변경의 비즈니스 영향도를 더 정확하게 설명합니다.

### Markdown 파일 일괄 등록

```python
# Python 스크립트로 실행
from agents.nodes.domain_explainer import DomainDocIngester

ingester = DomainDocIngester()

# 폴더 내 모든 .md 파일 인덱싱
count = ingester.ingest_markdown_dir("./내부문서/")
print(f"{count}개 청크 등록 완료")
```

### 단일 텍스트 등록

```python
ingester.ingest_text(
    text="VIP 고객은 전체 주문의 15% 할인을 받습니다. 골드 고객은 10%...",
    source="할인 정책 v3.2"
)
```

### 지원 포맷

- `.md` — Markdown 파일 (권장)
- 직접 텍스트 입력

> 등록된 문서는 ChromaDB에 벡터로 저장되며, 분석 시 자동으로 참조됩니다.
> 재시작 후에도 데이터가 유지됩니다 (`.chroma/` 폴더에 영구 저장).

---

## 9. 컨벤션 룰 커스터마이징

`config/conventions.yaml` 파일을 수정하여 팀의 코딩 규칙을 정의할 수 있습니다.

### 파일 구조

```yaml
naming:
  rules:
    - id: snake_case_functions
      description: "함수명은 snake_case를 사용한다"
      severity: warning   # error | warning | info

error_handling:
  rules:
    - id: no_bare_except
      description: "bare except: 사용 금지"
      severity: error     # error는 머지 차단 권장
```

### 심각도 레벨

| 레벨 | 의미 | 색상 |
|------|------|------|
| `error` | 반드시 수정 (머지 차단 권장) | 🔴 빨간색 |
| `warning` | 수정 권장 | 🟡 노란색 |
| `info` | 참고사항 | 🔵 파란색 |

### 새 규칙 추가 예시

```yaml
code_quality:
  rules:
    - id: no_todo_comments
      description: "TODO 주석은 이슈로 등록 후 제거한다"
      severity: info

    - id: max_file_length
      description: "파일은 300줄을 넘기지 않는다"
      threshold: 300
      severity: warning
```

> 파일 수정 후 서버를 재시작하면 즉시 적용됩니다.

---

## 10. 자주 묻는 질문 (FAQ)

### Q. 분석이 시작되지 않아요

**확인 사항:**
- `.env` 파일에 `ANTHROPIC_API_KEY`와 `GITHUB_TOKEN`이 올바르게 입력되었나요?
- GitHub Token에 해당 레포지토리 접근 권한이 있나요?
- 백엔드 서버가 실행 중인가요? (`http://localhost:8000/health` 에서 확인)

### Q. 테스트가 계속 실패해요

자동 생성된 테스트는 외부 의존성(DB, API 등)이 있는 경우 실패할 수 있습니다.
Agent가 최대 3회 자동 수정을 시도하며, 모두 실패하면 실패 원인을 코멘트에 포함합니다.

테스트 탭에서 오류 로그를 확인하고 채팅에서 "테스트 실패 원인 분석해줘"라고 물어보세요.

### Q. Docker가 없어도 되나요?

네. Docker가 없으면 테스트 실행이 로컬 환경(시스템 Python)에서 직접 실행됩니다.
격리가 되지 않으므로 보안에 주의하세요. 프로덕션에서는 Docker 사용을 권장합니다.

### Q. 도메인 설명이 "관련 정보 없음"으로 나와요

도메인 문서가 ChromaDB에 등록되지 않은 경우입니다.
[8번 섹션](#8-도메인-문서-등록하기-rag)을 참고해 내부 문서를 등록하세요.

### Q. Slack 승인이 GitHub에 반영되지 않아요

**확인 사항:**
- `SLACK_SIGNING_SECRET`이 올바른지 확인
- Slack App의 Interactivity Request URL이 `/slack/events`를 가리키는지 확인
- 서버가 외부에서 접근 가능한지 확인 (ngrok 사용 또는 실제 도메인 필요)

### Q. 분석 속도가 느려요

- LLM 호출이 많을수록 느립니다. 빠른 분석을 원하면 `.env`에서:
  ```bash
  ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # 더 빠른 모델
  ```
- diff가 8000자 이상이면 LLM 컨벤션 체크가 자동으로 스킵됩니다 (AST만 실행).

### Q. 여러 PR을 동시에 분석할 수 있나요?

네. API 서버는 비동기로 동작하므로 동시에 여러 PR을 분석할 수 있습니다.
단, 같은 PR에 대한 중복 요청은 캐시로 방지됩니다.

---

## 부록 — 키보드 단축키

| 단축키 | 동작 |
|--------|------|
| `Enter` | PR 분석 시작 (헤더 입력창에서) |
| `Enter` | 채팅 메시지 전송 |
| `Shift + Enter` | 채팅 줄바꿈 |

---

*문의 및 기여: [GitHub Issues](https://github.com) | Smart PR Inspector v1.0.0*
