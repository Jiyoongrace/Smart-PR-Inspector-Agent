# 도메인 문서 (RAG용)

Smart PR Inspector Agent 프로젝트의 비즈니스 컨텍스트를 담은 문서입니다.
ChromaDB에 인덱싱되어 PR 분석 시 비즈니스 영향도 설명에 활용됩니다.

## 문서 목록

| 파일 | 용도 |
|------|------|
| `business-glossary.md` | Agent 파이프라인, 분석 결과, 외부 연동 용어 사전 |
| `product-features.md` | 8개 핵심 기능 명세 |
| `business-rules.md` | 파이프라인/API/LLM/프론트엔드 비즈니스 규칙 10개 |
| `team-policy.md` | 배포, 리뷰, 장애 대응, 브랜치, 테스트 정책 |
| `architecture-decisions.md` | 7개 ADR (LangGraph, SSE, RAG 등) |
| `equipment-spec.md` | GitHub/Claude/Redis/ChromaDB 등 인프라 제약조건 |
| `customer-spec.md` | 사용자 유형별 요구사항 및 품질 SLA |
| `design-criteria.md` | 컨벤션/시나리오/리스크 판정 기준, LLM 파라미터, 노드 타임아웃 |

## 문서 인덱싱

```bash
docker-compose up -d chromadb

python3 -c "
from agents.nodes.domain_explainer import DomainDocIngester
count = DomainDocIngester().ingest_markdown_dir('./docs/domain/')
print(f'{count}개 청크 인덱싱 완료')
"
```
