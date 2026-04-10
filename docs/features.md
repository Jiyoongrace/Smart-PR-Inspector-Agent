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

## 3. 코드 영향도 분석 (Static Analysis + 비즈니스 임팩트)

**What**: 변경된 함수가 어떤 모듈/함수에서 호출되는지 추적하고, 비즈니스 관점의 영향도를 분석

**How**:
1. `ast` 모듈로 전체 프로젝트 파싱 → 호출 그래프 생성
2. 변경된 함수를 시작점으로 DFS/BFS 탐색
3. 영향받는 파일 리스트 + 호출 체인 반환
4. **LLM 비즈니스 영향도 분석**: 변경 코드를 시니어 엔지니어 관점에서 비즈니스 임팩트 분석
   - 사용자 체감 변화 분석
   - 영향받는 비즈니스 기능 목록
   - 장애 시 비즈니스 리스크 평가
   - 배포 전 체크리스트 생성

**출력 예시**:
```markdown
### 🔗 영향도 분석
`calculate_discount()` 변경 시 영향받는 모듈:
- `order_service.py` (Line 145: create_order)
- `invoice_generator.py` (Line 78: generate_invoice)
- `api/v1/checkout.py` (Line 203: POST /checkout)

⚠️ **주의**: API 엔드포인트 변경 감지됨 → Swagger 업데이트 필요

### 💼 비즈니스 영향도 (시니어 관점)
**요약**: 할인 정책 계산 로직 변경으로 주문 금액에 직접 영향
**사용자 체감**: 기존 할인율과 달라질 수 있어 고객 문의 증가 가능
**배포 전 체크리스트**:
1. QA 환경에서 할인 시나리오별 금액 검증
2. 기존 주문 데이터와 역산 비교
3. CS 팀에 할인 정책 변경 사전 공유
```

---

## 4. 도메인 기반 비즈니스 영향도 설명 (Hybrid RAG)

**What**: Hybrid RAG (Dense + Sparse + Re-ranking)으로 도메인 문서를 정밀 검색하여 비즈니스 영향도 설명

**How**:
1. 도메인 문서를 ChromaDB(Dense) + BM25(Sparse)에 동시 인덱싱
2. PR title + diff를 쿼리로 **Dense 검색**(의미적 유사도) + **Sparse 검색**(키워드 매칭)
3. **RRF (Reciprocal Rank Fusion)** 로 두 결과를 통합
4. **Cross-Encoder 기반 Re-ranking** (ms-marco-MiniLM)으로 최종 Top-5 정밀 정렬
5. 검색된 문서 + 코드 Diff를 LLM에게 전달 → 비즈니스 영향도 200자 설명 생성

**Hybrid의 장점**:
- `validate_card` 같은 함수명은 Sparse(BM25)가 정확히 매칭
- "결제 프로세스 리팩토링" 같은 의미는 Dense(벡터)가 이해
- Re-ranking으로 노이즈 문서 제거, 관련도 높은 문서만 LLM에 전달

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

## 6. PR 승인 / 머지 워크플로우

**What**: 분석 완료 후 UI에서 바로 PR 승인 및 머지 처리 가능

### 6-A. 웹 UI에서 직접 처리 (권장)

분석 결과 **개요 탭** 하단 "PR 액션" 패널에서:

| 버튼 | 동작 |
|------|------|
| **PR 승인** | GitHub에 Approve Review 제출 |
| **PR 머지** | 선택한 방식으로 GitHub PR 머지 |
| **GitHub에서 보기** | PR 페이지로 이동 |

**머지 방식 선택**:
- `Squash Merge` (기본) — 커밋을 1개로 합쳐서 머지
- `Merge Commit` — 모든 커밋 이력 유지
- `Rebase Merge` — 선형 이력 유지

### 6-B. REST API 직접 호출

```bash
# PR 승인
curl -X POST "http://localhost:8000/api/approve-pr?repo=owner/repo&pr_number=1234"

# PR 머지 (squash)
curl -X POST "http://localhost:8000/api/merge-pr?repo=owner/repo&pr_number=1234&merge_method=squash"
```

### 6-C. Slack 연동 (선택)

**What**: Slack에서 PR 승인/거부를 처리 가능

**How**:
1. Agent가 PR 분석 완료 후 Slack 채널에 메시지 전송
2. Slack Block Kit으로 "승인", "수정 요청", "상세 보기" 버튼 제공
3. 버튼 클릭 시 Slack Webhook → GitHub API로 Review 제출

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

## 9. AI 기반 PR 자동 생성 (신규)

**What**: 브랜치 간 커밋 내역을 Claude로 분석하여 PR 제목 + 본문을 자동 작성 후 GitHub PR 생성

**How**:
1. 사이드바 **"생성" 탭** 클릭
2. 레포지토리 (`owner/repo`), Head 브랜치, Base 브랜치 입력
3. Draft 여부 선택 후 "PR 생성" 버튼 클릭
4. Claude가 커밋 목록 분석 → 제목/변경 사항/체크리스트 자동 작성
5. GitHub PR 생성 완료 → PR 번호 + 링크 표시

**폴백**: Claude API 호출 실패 시 커밋 메시지 기반으로 자동 생성

**REST API**:
```bash
curl -X POST http://localhost:8000/api/create-pr \
  -H "Content-Type: application/json" \
  -d '{"repo":"owner/repo","head":"feature/my-feature","base":"main","draft":false}'
```

---

## 10. 아키텍처 룰 점검 + HITL 승인 (신규)

**What**: 아키텍처 수준의 심각한 위반 자동 감지 + 시니어 리뷰어 승인 대기

**How**:
1. 레이어 위반 검사 (API에서 직접 DB 접근)
2. 보안 위반 검사 (하드코딩된 시크릿/API 키)
3. 구조 위반 검사 (God Class, 순환 참조)
4. 위반 발견 시 시니어 리뷰어에게 Slack/Email 알림
5. 승인 → 테스트 진행 / 반려 → PR 즉시 반려 (Merge Block)

**왜 필요한가**: AI가 모든 것을 결정하게 두지 않고, 아키텍처 의사결정은 반드시 인간의 통제 하에 둡니다.

---

## 11. 병렬 처리 (Fork/Join)

**What**: Convention 검증과 Test 생성을 동시에 실행하여 분석 시간 단축

**How**:
1. `fetch` 완료 후 두 갈래로 분기 (Fork)
2. Branch A: convention (AST + RAG 룰 + LLM 검증)
3. Branch B: test_gen (BDD 시나리오 생성)
4. 두 작업 모두 완료 후 합류 (Join)
5. `arch_review` → `test_run`으로 진행

**효과**: convention(~15초) + test_gen(~20초) = 순차 35초 → 병렬 20초 (**43% 단축**)

---

## 12. PR Health Score (특색 기능)

**What**: PR 건강도를 100점 만점으로 측정하여 S~F 등급 판정 + 머지 권장 여부 자동 결정

**How**:
1. 4영역 각 25점 만점으로 점수 계산:
   - 📋 **컨벤션** (25점): 위반 0건=25점, error당 -8점, warning당 -3점
   - 🧪 **테스트** (25점): 시나리오 통과율 × 25
   - 🔗 **영향도** (25점): 리스크 low=25, medium=18, high=10, critical=3
   - 📖 **도메인** (25점): RAG 문서 기반 설명=25, 코드 추론=18, 없음=8
2. 총점에 따른 등급: S(90+), A(80+), B(65+), C(50+), D(30+), F(<30)
3. GitHub 코멘트에 프로그레스 바 카드로 시각화
4. Slack 메시지에도 점수 카드 포함

**출력 예시**:
```
🏆 PR Health Score: S (95/100) — 즉시 머지 가능

| 영역     | 점수          |
|----------|---------------|
| 📋 컨벤션 | ██████████ 25/25 |
| 🧪 테스트 | ████████░░ 20/25 |
| 🔗 영향도 | ██████████ 25/25 |
| 📖 도메인 | ██████████ 25/25 |
```

---

## 13. 팀 컨벤션/도메인 문서 업로드 (RAG 활용)

**What**: 팀별 코드 컨벤션 가이드나 도메인 규칙 문서를 업로드하면, PR 분석 시 Hybrid RAG로 검색하여 활용

**How**:
1. `POST /api/rag/upload/convention` — 팀 컨벤션 문서(.md) 업로드
2. Hybrid RAG (Dense + BM25 Sparse)에 동시 인덱싱
3. PR 분석 시 convention 노드에서 관련 규칙을 RAG 검색
4. 검색된 팀 규칙을 LLM 프롬프트에 컨텍스트로 전달
5. 팀 고유 규칙까지 반영한 정밀 컨벤션 검증 수행

**활용 시나리오**:
- "우리 팀은 controller에서 직접 DB 접근을 금지합니다" → 문서 업로드 → PR에서 위반 시 자동 감지
- "API 응답은 반드시 camelCase로 반환해야 합니다" → 문서 업로드 → 컨벤션 검증에 반영

---

## 14. 실시간 분석 대시보드

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
