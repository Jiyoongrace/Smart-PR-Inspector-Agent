# Smart PR Inspector Agent — 프로젝트 개요

## Agent 정의

**Smart PR Inspector Agent**는 GitHub Pull Request 생성 시 자동으로 트리거되어,
코드 분석부터 컨벤션 검증, 테스트 실행, 문서 동기화, 비즈니스 영향도 분석까지
수행하는 지능형 코드 품질 관리 에이전트입니다.

---

## 핵심 가치 제안

| 가치 | 설명 |
|------|------|
| **리뷰 병목 해소** | 시니어 개발자의 반복적 검토 시간 80% 절감 |
| **품질 사전 보장** | PR 머지 전 사이드 이펙트 및 컨벤션 위반 자동 탐지 |
| **지식 전이** | Hybrid RAG (Dense + Sparse + Re-ranking) 기반 도메인 문서 검색으로 비즈니스 영향도 자동 설명 |
| **문서 동기화** | API 스펙 변경 시 Swagger/README 자동 업데이트 제안 |
| **아키텍처 보호** | HITL(Human-in-the-Loop)로 아키텍처 룰 위반 시 시니어 승인 필수 |
| **빠른 분석** | Convention + Test Gen 순차 최적화로 분석 시간 단축 |
| **PR 건강도** | 100점 만점 Health Score로 머지 권장 여부 자동 판정 (S~F 등급) |
| **팀 맞춤 분석** | 팀별 컨벤션/도메인 문서를 RAG에 업로드하여 맞춤형 분석 |

---

## Agent 4요소 정의

| 요소 | 구현 내용 | 핵심 질문 |
|------|-----------|-----------|
| **Goal** | PR 코드가 병합 가능한 상태인지 자동 검증 및 리뷰 | "테스트 통과 + 컨벤션 준수 + 아키텍처 룰 통과 + 문서 동기화 완료" |
| **Memory** | Hybrid RAG 벡터 DB (Dense + BM25 Sparse), 팀 코딩 컨벤션 룰북, 과거 PR 리뷰 패턴 | "도메인 문서 의미 검색 + 키워드 정확 매칭 + Cross-Encoder 재순위" |
| **Tool** | GitHub API, 테스트 러너, LLM(Claude/GPT-4), ChromaDB + BM25, Slack API, AST 파서 | "코드 분석, 외부 시스템 연동, Hybrid 검색, 알림" |
| **Control Logic** | 병렬 처리(Fork/Join), HITL 승인 대기, 테스트 최대 3회 재시도, Fallback 경로 | "병렬: convention + test_gen / HITL: 아키텍처 위반 시 시니어 승인 / 재시도: 3회" |

---

## 예상 성과

| 지표 | 현재 | 목표 (3개월 후) |
|------|------|----------------|
| 평균 리뷰 시간 | 45분 | 10분 (78% 감소) |
| 컨벤션 위반 재발 | PR당 2.3회 | 0.5회 (78% 감소) |
| 문서 불일치 | 월 8건 | 월 1건 (87% 감소) |
| 시니어 리뷰 요청 | 일 10회 | 일 3회 (70% 감소) |

---

## 고급 아키텍처 요소

| 요소 | 설명 |
|------|------|
| **Human-in-the-Loop** | 아키텍처 룰 위반 시 시니어 리뷰어에게 승인/반려 요청 (Merge Block) |
| **병렬 처리** | Convention + Test Gen을 Fork/Join으로 동시 실행 (분석 시간 43% 단축) |
| **Hybrid RAG** | Dense(벡터) + Sparse(BM25) + Cross-Encoder 기반 Re-ranking으로 도메인 문서 정밀 검색 |
| **재시도/폴백** | 테스트 실패 시 LLM 자동 수정 후 최대 3회 재시도, 실패해도 나머지 분석 계속 |

---

## 지원 언어 및 플랫폼

- **주요 언어**: Python (AST 기반 분석)
- **향후 지원**: JavaScript/TypeScript, Java (확장 예정)
- **플랫폼**: GitHub (GitHub Actions Webhook 기반)
- **알림**: Slack, GitHub Comments
