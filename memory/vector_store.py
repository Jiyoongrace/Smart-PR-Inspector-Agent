"""
벡터 스토어 관리 (ChromaDB)
도메인 문서 인덱싱 및 검색
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB 기반 도메인 문서 벡터 스토어"""

    def __init__(self, collection_name: str = "domain_docs"):
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_client(self):
        if self._client is None:
            import chromadb

            use_http = os.getenv("CHROMA_HOST") and os.getenv("CHROMA_HOST") != "localhost"

            if use_http:
                self._client = chromadb.HttpClient(
                    host=os.getenv("CHROMA_HOST", "localhost"),
                    port=int(os.getenv("CHROMA_PORT", "8001")),
                )
            else:
                # 로컬 퍼시스턴트 DB
                persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./.chroma")
                self._client = chromadb.PersistentClient(path=persist_dir)

        return self._client

    def _get_collection(self):
        if self._collection is None:
            from chromadb.utils import embedding_functions
            client = self._get_client()
            ef = embedding_functions.DefaultEmbeddingFunction()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=ef,
            )
        return self._collection

    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """문서를 벡터 DB에 추가"""
        collection = self._get_collection()

        if ids is None:
            ids = [f"doc_{i}_{hash(doc)}" for i, doc in enumerate(documents)]

        if metadatas is None:
            metadatas = [{}] * len(documents)

        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"{len(documents)}개 문서 인덱싱 완료")

    def search(
        self,
        query: str,
        n_results: int = 3,
    ) -> List[dict]:
        """유사 문서 검색"""
        collection = self._get_collection()

        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
        )

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            output.append({
                "content": doc,
                "metadata": meta,
                "score": 1 - dist,  # 유사도 점수 (높을수록 유사)
            })

        return output

    def ingest_directory(self, dir_path: str) -> int:
        """디렉토리 내 Markdown 파일 일괄 인덱싱"""
        from pathlib import Path

        docs = []
        metas = []
        ids = []

        for md_file in Path(dir_path).rglob("*.md"):
            with open(md_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # 1000자 청크로 분할
            for i, chunk in enumerate(_chunk_text(content)):
                docs.append(chunk)
                metas.append({"source": str(md_file), "chunk": i})
                ids.append(f"{md_file.stem}_{i}")

        if docs:
            self.add_documents(docs, metas, ids)

        return len(docs)

    def count(self) -> int:
        """저장된 문서 수"""
        return self._get_collection().count()


def _chunk_text(text: str, chunk_size: int = 1000) -> List[str]:
    return [
        text[i:i + chunk_size].strip()
        for i in range(0, len(text), chunk_size)
        if text[i:i + chunk_size].strip()
    ]


# 전역 싱글턴
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
