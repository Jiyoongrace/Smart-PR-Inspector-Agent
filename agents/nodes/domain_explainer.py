"""
RAG 기반 도메인 설명 노드
Hybrid RAG (Dense + Sparse BM25) + Cross-Encoder Re-ranking으로
비즈니스 영향도 설명 생성
"""

import logging
import os
from typing import List, Tuple

from agents.state import AgentState, NodeStatus

logger = logging.getLogger(__name__)


def domain_explainer_node(state: AgentState) -> AgentState:
    """Hybrid RAG 도메인 문서 검색 후 비즈니스 영향도 설명 생성"""
    state.node_status.domain_explain = NodeStatus.RUNNING

    if not state.pr_data:
        state.node_status.domain_explain = NodeStatus.SKIPPED
        return state

    try:
        # Hybrid RAG 검색 (Dense + Sparse + Re-ranking)
        docs, sources = _hybrid_search_domain_docs(
            query=f"{state.pr_data.title}\n{state.pr_data.diff[:300]}"
        )

        # LLM으로 비즈니스 영향도 설명 생성
        explanation = _generate_explanation(
            pr_title=state.pr_data.title,
            diff_snippet=state.pr_data.diff[:2000],
            domain_docs=docs,
        )

        state.domain_explanation = explanation
        state.domain_sources = sources

        state.node_status.domain_explain = NodeStatus.SUCCESS
        logger.info(f"도메인 설명 생성 완료 ({len(docs)}개 문서 참조, Hybrid RAG)")

    except Exception as e:
        logger.warning(f"도메인 설명 생성 실패 (스킵): {e}")
        state.domain_explanation = None
        state.domain_sources = []
        state.node_status.domain_explain = NodeStatus.SKIPPED

    return state


def _hybrid_search_domain_docs(query: str) -> Tuple[List[str], List[str]]:
    """
    Hybrid RAG 검색 파이프라인:
    1. Dense (ChromaDB 벡터 검색) — 의미적 유사도
    2. Sparse (BM25 키워드 검색) — 정확한 용어 매칭
    3. RRF (Reciprocal Rank Fusion) — 결과 통합
    4. Cross-Encoder Re-ranking — 최종 정밀 정렬
    """
    try:
        from memory.vector_store import get_vector_store

        store = get_vector_store()

        if store.count() == 0:
            logger.info("도메인 문서 DB가 비어있음 — 벡터 검색 스킵")
            return [], []

        # Hybrid 검색 (Dense + Sparse → RRF → Re-ranking)
        results = store.search(
            query=query,
            n_results=5,
            use_reranking=True,
        )

        docs = [r["content"] for r in results]
        sources = [
            r["metadata"].get("source", "알 수 없음")
            for r in results
            if r.get("metadata")
        ]

        # 중복 소스 제거
        sources = list(dict.fromkeys(sources))

        logger.info(
            f"Hybrid RAG 검색: {len(results)}개 문서 반환 "
            f"(Re-ranking 적용)"
        )
        return docs, sources

    except Exception as e:
        logger.debug(f"Hybrid RAG 검색 실패, Dense-only 폴백: {e}")
        return _fallback_dense_search(query)


def _fallback_dense_search(query: str) -> Tuple[List[str], List[str]]:
    """Hybrid 실패 시 기존 Dense 검색으로 폴백"""
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST", "localhost"),
            port=int(os.getenv("CHROMA_PORT", "8001")),
        )
        ef = embedding_functions.DefaultEmbeddingFunction()
        collection = client.get_or_create_collection(
            name="domain_docs",
            embedding_function=ef,
        )

        if collection.count() == 0:
            return [], []

        results = collection.query(
            query_texts=[query],
            n_results=min(3, collection.count()),
        )

        docs = results["documents"][0] if results["documents"] else []
        sources = []
        if results.get("metadatas") and results["metadatas"][0]:
            sources = [
                meta.get("source", "알 수 없음")
                for meta in results["metadatas"][0]
            ]

        return docs, sources

    except Exception as e:
        logger.debug(f"Dense 폴백도 실패: {e}")
        return [], []


def _generate_explanation(
    pr_title: str,
    diff_snippet: str,
    domain_docs: List[str],
) -> str:
    """LLM으로 비즈니스 영향도 설명 생성"""
    from config.llm import call_llm

    domain_context = ""
    if domain_docs:
        domain_context = "\n\n관련 도메인 문서:\n" + "\n---\n".join(domain_docs[:5])

    prompt = f"""다음 코드 변경이 비즈니스적으로 어떤 의미인지 200자 이내로 한국어로 설명하세요.
기술적 설명보다 비즈니스/사용자 관점에서 설명하고, 주의사항이 있다면 언급하세요.
관련 정보가 없으면 코드만 보고 추론하세요.

PR 제목: {pr_title}

코드 변경:
{diff_snippet[:1500]}
{domain_context}

응답 형식:
- 첫 문장: 이 변경이 무엇을 하는지
- 둘째 문장: 사용자/비즈니스에 미치는 영향
- (있다면) 주의사항"""

    return call_llm(prompt, max_tokens=512)


class DomainDocIngester:
    """
    도메인 문서를 Hybrid RAG 인덱스에 인덱싱하는 유틸리티
    Dense (ChromaDB) + Sparse (BM25) 동시 인덱싱
    사용법: DomainDocIngester().ingest_markdown_dir("./docs/domain")
    """

    def __init__(self):
        from memory.vector_store import get_vector_store
        self._store = get_vector_store()

    def ingest_markdown_dir(self, dir_path: str) -> int:
        """디렉토리 내 모든 Markdown 파일 Hybrid 인덱싱"""
        count = self._store.ingest_directory(dir_path)
        logger.info(f"{count}개 청크 Hybrid 인덱싱 완료 (Dense + Sparse)")
        return count

    def ingest_text(self, text: str, source: str = "manual") -> None:
        """단일 텍스트 인덱싱"""
        from memory.vector_store import _chunk_text
        chunks = _chunk_text(text)
        ids = [f"{source}_{i}" for i in range(len(chunks))]
        metas = [{"source": source, "chunk": i} for i in range(len(chunks))]
        self._store.add_documents(chunks, metas, ids)
