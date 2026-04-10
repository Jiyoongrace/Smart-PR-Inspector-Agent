# 팀 정책

## 배포

- 운영 배포: 평일 오전(10:00~12:00)만 허용
- 핫픽스: 2인 이상 승인 후 즉시 배포 가능
- 프롬프트(config/prompts.py) 변경: 반드시 기존 대비 A/B 비교 후 반영
- 환경변수 추가 시: .env.example과 CLAUDE.md 동시 업데이트

## 코드 리뷰

- 모든 PR: 최소 1인 승인 필요
- Agent 노드 추가/수정: orchestrator.py 엣지 변경 확인 필수
- 새 노드 추가: agents/nodes/__init__.py에 export 추가 필수
- 프롬프트 변경: 시나리오 테스트로 품질 확인

## 장애 대응

- P1 (전체 중단): 30분 내 대응
- P2 (특정 노드 실패): 2시간 내 대응
- P3 (분석 정확도): 당일 내 프롬프트 튜닝
- P4 (UI 문제): 다음 스프린트

## 코딩 컨벤션 (Python)

- 함수: snake_case, 클래스: PascalCase, 상수: UPPER_SNAKE_CASE
- 타입 힌트 + 한국어 docstring 필수
- print() 금지 → logging 사용
- bare except 금지, 함수 50줄 이하
- 매직 넘버 → 상수 분리

## 코딩 컨벤션 (TypeScript/React)

- "use client" 필요한 컴포넌트만
- Props는 별도 interface 정의
- 전역 상태: useAppStore() 훅으로만 접근
- Tailwind CSS + cn() 유틸리티
