"""
RAG 기반 도메인 설명 노드
ChromaDB 벡터 검색 + Claude LLM으로 비즈니스 영향도 설명
"""

import logging
import os
from typing import List

from agents.state import AgentState, NodeStatus

logger = logging.getLogger(__name__)


def domain_explainer_node(state: AgentState) -> AgentState:
    """도메인 문서 검색 후 비즈니스 영향도 설명 생성"""
    state.node_status.domain_explain = NodeStatus.RUNNING

    if not state.pr_data:
        state.node_status.domain_explain = NodeStatus.SKIPPED
        return state

    try:
        # ChromaDB에서 관련 문서 검색
        docs, sources = _search_domain_docs(
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
        logger.info(f"도메인 설명 생성 완료 ({len(docs)}개 문서 참조)")

    except Exception as e:
        # RAG 실패는 치명적이지 않으므로 경고만
        logger.warning(f"도메인 설명 생성 실패 (스킵): {e}")
        state.domain_explanation = None
        state.domain_sources = []
        state.node_status.domain_explain = NodeStatus.SKIPPED

    return state


def _search_domain_docs(query: str) -> tuple[List[str], List[str]]:
    """ChromaDB에서 관련 도메인 문서 벡터 검색"""
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST", "localhost"),
            port=int(os.getenv("CHROMA_PORT", "8001")),
        )

        # 임베딩 함수 (Anthropic embeddings 또는 기본 사용)
        ef = embedding_functions.DefaultEmbeddingFunction()

        collection = client.get_or_create_collection(
            name="domain_docs",
            embedding_function=ef,
        )

        if collection.count() == 0:
            logger.info("도메인 문서 DB가 비어있음 - 벡터 검색 스킵")
            return [], []

        results = collection.query(
            query_texts=[query],
            n_results=min(3, collection.count()),
        )

        docs = results["documents"][0] if results["documents"] else []
        sources = []

        if results.get("metadatas") and results["metadatas"][0]:
            sources = [
                meta.get("source", meta.get("title", "알 수 없음"))
                for meta in results["metadatas"][0]
            ]

        return docs, sources

    except Exception as e:
        logger.debug(f"ChromaDB 연결 실패: {e}")
        return [], []


def _generate_explanation(
    pr_title: str,
    diff_snippet: str,
    domain_docs: List[str],
) -> str:
    """Claude로 비즈니스 영향도 설명 생성"""
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    domain_context = ""
    if domain_docs:
        domain_context = "\n\n관련 도메인 문서:\n" + "\n---\n".join(domain_docs[:3])

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

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


class DomainDocIngester:
    """
    도메인 문서를 ChromaDB에 인덱싱하는 유틸리티
    사용법: DomainDocIngester().ingest_markdown_dir("./docs")
    """

    def __init__(self):
        import chromadb
        from chromadb.utils import embedding_functions

        self.client = chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST", "localhost"),
            port=int(os.getenv("CHROMA_PORT", "8001")),
        )
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="domain_docs",
            embedding_function=self.ef,
        )

    def ingest_markdown_dir(self, dir_path: str) -> int:
        """디렉토리 내 모든 Markdown 파일 인덱싱"""
        from pathlib import Path

        docs_dir = Path(dir_path)
        count = 0

        for md_file in docs_dir.rglob("*.md"):
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 청크 분할 (최대 1000자)
            chunks = _chunk_text(content, chunk_size=1000)

            for i, chunk in enumerate(chunks):
                self.collection.add(
                    documents=[chunk],
                    metadatas=[{"source": str(md_file), "chunk": i}],
                    ids=[f"{md_file.stem}_{i}"],
                )
                count += 1

        logger.info(f"{count}개 청크 인덱싱 완료")
        return count

    def ingest_text(self, text: str, source: str = "manual") -> None:
        """단일 텍스트 인덱싱"""
        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            self.collection.add(
                documents=[chunk],
                metadatas=[{"source": source, "chunk": i}],
                ids=[f"{source}_{i}"],
            )


def _chunk_text(text: str, chunk_size: int = 1000) -> List[str]:
    """텍스트를 청크로 분할"""
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks
