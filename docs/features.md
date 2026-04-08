# 주요 기능 명세

## 1. 코드 변경 분석 및 컨벤션 검증

**What**: PR에서 변경된 코드를 AST 파싱하여 사내 컨벤션 룰북과 대조

**How**:
1. `unidiff`로 Diff 파싱 → 추가/수정된 라인 추출
2. `ast.parse()`로 Python AST 생성
3. 컨벤션 룰북 (YAML)과 패턴 매칭
4. 위반 시 라인 번호 + 규칙명 + 제안 코드 반환
5. LLM으로 복잡한 규칙 검증 (가독성, 로직 중복 등)

**출력 예시**:
```markdown
### ❌ 컨벤션 위반 (3건)
- Line 42: 함수명 `getData` → `get_data` (snake_case 규칙)
- Line 58: 매직넘버 `7` → 상수로 분리 권장
- Line 103: 타입 힌트 누락 → `def process(data: dict) -> List[str]`
```

---

## 2. AI 기반 테스트 자동 생성 및 실행

**What**: 변경된 함수에 대해 LLM이 pytest 코드를 생성하고 Docker에서 실행

**How**:
1. 변경 함수의 시그니처 + docstring 추출
2. Claude/GPT-4에게 "이 함수를 검증하는 pytest 코드 작성" 프롬프트
3. 생성된 코드를 임시 파일로 저장
4. Docker 컨테이너에서 `pytest --tb=short` 실행 (타임아웃 5분)
5. 실패 시 에러 로그를 다시 LLM에 전달 → 코드 수정 (최대 3회)

---

## 3. 코드 영향도 분석 (Static Analysis)

**What**: 변경된 함수가 어떤 모듈/함수에서 호출되는지 추적

**How**:
1. `ast` 모듈로 전체 프로젝트 파싱 → 호출 그래프 생성
2. 변경된 함수를 시작점으로 DFS/BFS 탐색
3. 영향받는 파일 리스트 + 호출 체인 반환

**출력 예시**:
```markdown
### 🔗 영향도 분석
`calculate_discount()` 변경 시 영향받는 모듈:
- `order_service.py` (Line 145: create_order)
- `invoice_generator.py` (Line 78: generate_invoice)
- `api/v1/checkout.py` (Line 203: POST /checkout)

⚠️ **주의**: API 엔드포인트 변경 감지됨 → Swagger 업데이트 필요
```

---

## 4. 도메인 기반 비즈니스 영향도 설명 (RAG)

**What**: 내부 도메인 문서를 검색하여 변경이 비즈니스적으로 어떤 의미인지 설명

**How**:
1. Notion/Confluence 문서를 크롤링 → 벡터 DB (ChromaDB) 저장
2. 변경된 함수명 + 주변 코드를 쿼리로 유사 문서 검색
3. 검색된 문서 + 코드 Diff를 LLM에게 전달
4. 비즈니스 영향도 300자 이내 설명 생성

**출력 예시**:
```markdown
### 📖 도메인 영향도
이번 변경은 **주문 취소 시 포인트 환급 정책**을 수정합니다.
기존에는 결제 금액 기준으로 환급했으나, 변경 후에는 실제 사용한 포인트만 환급됩니다.
이는 "2024 Q2 포인트 제도 개편"과 연관되며, CS 팀과 사전 조율이 필요합니다.

📎 참고 문서: [Confluence - 포인트 정책 v3.2]
```

---

## 5. API 스펙 변경 감지 및 문서 동기화

**What**: FastAPI/Flask 엔드포인트 변경 시 Swagger/README 업데이트 제안

**How**:
1. `ast` 파서로 `@app.post()` 데코레이터 + 함수 시그니처 추출
2. 기존 `swagger.yaml` / `openapi.json` 파싱
3. Diff 비교 → 추가/변경/삭제된 필드 탐지
4. Jinja2 템플릿으로 업데이트 초안 생성
5. PR 코멘트에 "제안된 Swagger 변경사항" 첨부

---

## 6. Slack 연동 승인 워크플로우

**What**: 시니어가 Slack에서 PR 승인/거부를 처리 가능

**How**:
1. Agent가 PR 분석 완료 후 Slack 채널에 메시지 전송
2. Slack Block Kit으로 "승인", "수정 요청", "상세 보기" 버튼 제공
3. 버튼 클릭 시 Slack Webhook → GitHub API로 Review 제출
4. 승인 시 자동 머지 (옵션)

**Slack 메시지 예시**:
```
🤖 Smart PR Inspector

PR #1234: "재고 차감 로직 개선"
✅ 컨벤션: 통과
✅ 테스트: 5/5 통과
⚠️ 영향도: 3개 모듈 변경
📄 Swagger 업데이트 필요

[승인] [수정 요청] [상세 보기]
```

---

## 7. 버그 수정 검증 테스트 생성

**What**: PR 제목/본문에 "Fix #123" 패턴이 있으면 해당 이슈를 재현하는 테스트 생성

**How**:
1. GitHub Issue API로 이슈 내용 조회
2. 이슈 설명 + 재현 단계를 LLM에게 전달
3. "이 버그를 재현하는 테스트 코드" 생성 요청
4. 수정 전/후 코드에서 Fail → Pass 확인

---

## 8. 메모리 기반 학습 (과거 리뷰 패턴 반영)

**What**: 같은 개발자의 과거 PR 리뷰 이력을 학습하여 맞춤형 피드백

**How**:
1. PostgreSQL/Redis에 `{author: 리뷰 코멘트}` 이력 저장
2. 새 PR 분석 시 작성자의 과거 위반 패턴 조회
3. 개인화된 피드백 강화

**출력 예시**:
```markdown
### 💡 맞춤 제안 (Based on your history)
과거 3회의 PR에서 `Exception` 대신 구체적 예외를 사용하지 않은 사례가 있었습니다.
이번 PR의 Line 67에서도 동일한 패턴이 발견되었습니다.
```

---

## 9. 실시간 분석 대시보드 (신규)

**What**: 웹 UI에서 Agent 실행 과정을 실시간으로 모니터링

**How**:
1. SSE(Server-Sent Events)로 각 노드 실행 상태 스트리밍
2. 워크플로우 시각화 (노드별 진행 상태)
3. 결과 요약 + 상세 드릴다운

---

## 10. 복잡도 & 보안 스캔 (신규)

**What**: 코드 복잡도 분석 및 기본 보안 취약점 스캔

**How**:
1. `radon`으로 순환 복잡도(Cyclomatic Complexity) 측정
2. `bandit`으로 Python 보안 취약점 자동 스캔
3. 복잡도 임계값 초과 시 리팩토링 제안
