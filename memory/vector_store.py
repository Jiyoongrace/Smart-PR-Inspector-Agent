"""
벡터 스토어 관리 (ChromaDB + Hybrid RAG)
Dense(벡터) + Sparse(BM25) 검색 후 Cross-Encoder Re-ranking
"""

import logging
import math
import os
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── BM25 Sparse 검색기 ─────────────────────────────────────────────────


class BM25Index:
    """BM25 기반 Sparse 키워드 검색 인덱스"""

    def __init__(self):
        self._documents: List[str] = []
        self._metadatas: List[dict] = []
        self._ids: List[str] = []
        self._bm25 = None

    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """문서 추가 및 BM25 인덱스 재구축"""
        self._documents.extend(documents)
        self._metadatas.extend(metadatas or [{}] * len(documents))
        self._ids.extend(ids or [f"bm25_{i}" for i in range(len(documents))])
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """BM25 인덱스 재구축"""
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [_tokenize(doc) for doc in self._documents]
            self._bm25 = BM25Okapi(tokenized)
        except ImportError:
            logger.warning("rank_bm25 미설치 — Sparse 검색 비활성화")
            self._bm25 = None

    def search(self, query: str, n_results: int = 20) -> List[dict]:
        """BM25 키워드 검색"""
        if not self._bm25 or not self._documents:
            return []

        tokenized_query = _tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        # 상위 n_results개 인덱스 추출
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:n_results]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "content": self._documents[idx],
                    "metadata": self._metadatas[idx],
                    "score": float(scores[idx]),
                    "id": self._ids[idx],
                })
        return results

    def count(self) -> int:
        return len(self._documents)


def _tokenize(text: str) -> List[str]:
    """간단한 토큰화 (한국어 + 영어 혼합 지원)"""
    text = text.lower()
    # 영문/숫자/한글 단어 단위 분리
    tokens = re.findall(r"[a-z0-9_]+|[\uac00-\ud7a3]+", text)
    return [t for t in tokens if len(t) > 1]


# ── Cross-Encoder Re-ranker ────────────────────────────────────────────


class CrossEncoderReranker:
    """Cross-Encoder 기반 Re-ranking (sentence-transformers)"""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model = None
        self._model_name = model_name

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self._model_name)
                logger.info(f"Cross-Encoder 로드 완료: {self._model_name}")
            except ImportError:
                logger.warning("sentence-transformers 미설치 — Re-ranking 비활성화")

    def rerank(
        self, query: str, documents: List[dict], top_k: int = 5
    ) -> List[dict]:
        """Cross-Encoder로 문서 Re-ranking"""
        self._load_model()

        if not self._model or not documents:
            # 모델 없으면 기존 순서 유지
            return documents[:top_k]

        # (query, document) 페어 생성
        pairs = [(query, doc["content"]) for doc in documents]
        scores = self._model.predict(pairs)

        # 점수 부여 후 정렬
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        reranked = sorted(documents, key=lambda d: d["rerank_score"], reverse=True)
        return reranked[:top_k]


# ── Reciprocal Rank Fusion (RRF) ───────────────────────────────────────


def reciprocal_rank_fusion(
    dense_results: List[dict],
    sparse_results: List[dict],
    k: int = 60,
) -> List[dict]:
    """
    Dense + Sparse 결과를 RRF로 통합
    RRF score = Σ 1/(k + rank) for each retriever
    """
    doc_scores: Dict[str, float] = {}
    doc_map: Dict[str, dict] = {}

    # Dense 결과 순위 점수
    for rank, doc in enumerate(dense_results):
        doc_key = doc.get("id", doc["content"][:100])
        doc_scores[doc_key] = doc_scores.get(doc_key, 0) + 1.0 / (k + rank + 1)
        doc_map[doc_key] = doc

    # Sparse 결과 순위 점수
    for rank, doc in enumerate(sparse_results):
        doc_key = doc.get("id", doc["content"][:100])
        doc_scores[doc_key] = doc_scores.get(doc_key, 0) + 1.0 / (k + rank + 1)
        doc_map[doc_key] = doc

    # RRF 점수로 정렬
    sorted_keys = sorted(doc_scores, key=doc_scores.get, reverse=True)

    fused = []
    for key in sorted_keys:
        result = doc_map[key].copy()
        result["rrf_score"] = doc_scores[key]
        fused.append(result)

    return fused


# ── 메인 Hybrid Vector Store ──────────────────────────────────────────


class VectorStore:
    """
    Hybrid RAG 벡터 스토어
    Dense (ChromaDB) + Sparse (BM25) + Cross-Encoder Re-ranking
    """

    def __init__(self, collection_name: str = "domain_docs"):
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._bm25_index = BM25Index()
        self._reranker = CrossEncoderReranker()

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
        """Dense(ChromaDB) + Sparse(BM25) 동시 인덱싱"""
        collection = self._get_collection()

        if ids is None:
            ids = [f"doc_{i}_{hash(doc)}" for i, doc in enumerate(documents)]

        if metadatas is None:
            metadatas = [{}] * len(documents)

        # Dense 인덱싱 (ChromaDB)
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

        # Sparse 인덱싱 (BM25)
        self._bm25_index.add_documents(documents, metadatas, ids)

        logger.info(f"{len(documents)}개 문서 Hybrid 인덱싱 완료 (Dense + Sparse)")

    def search(
        self,
        query: str,
        n_results: int = 5,
        use_reranking: bool = True,
    ) -> List[dict]:
        """
        Hybrid 검색: Dense + Sparse → RRF 통합 → Cross-Encoder Re-ranking

        Args:
            query: 검색 쿼리
            n_results: 최종 반환 문서 수
            use_reranking: Cross-Encoder Re-ranking 사용 여부
        """
        # 1단계: Dense 검색 (ChromaDB 벡터 유사도)
        dense_results = self._dense_search(query, n_results=20)

        # 2단계: Sparse 검색 (BM25 키워드 매칭)
        sparse_results = self._bm25_index.search(query, n_results=20)

        if not dense_results and not sparse_results:
            return []

        # 3단계: RRF (Reciprocal Rank Fusion) 통합
        fused = reciprocal_rank_fusion(dense_results, sparse_results)

        # 4단계: Cross-Encoder Re-ranking (선택적)
        if use_reranking and fused:
            final = self._reranker.rerank(query, fused, top_k=n_results)
        else:
            final = fused[:n_results]

        logger.info(
            f"Hybrid 검색 완료: Dense={len(dense_results)}, "
            f"Sparse={len(sparse_results)}, "
            f"Fused={len(fused)}, Final={len(final)}"
        )
        return final

    def search_dense_only(
        self,
        query: str,
        n_results: int = 3,
    ) -> List[dict]:
        """Dense 검색만 수행 (기존 호환)"""
        return self._dense_search(query, n_results)

    def _dense_search(self, query: str, n_results: int = 20) -> List[dict]:
        """ChromaDB Dense 벡터 검색"""
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
        ids = results.get("ids", [[]])[0]

        for doc, meta, dist, doc_id in zip(docs, metas, distances, ids):
            output.append({
                "content": doc,
                "metadata": meta,
                "score": 1 - dist,
                "id": doc_id,
            })

        return output

    def ingest_directory(self, dir_path: str) -> int:
        """디렉토리 내 Markdown 파일 일괄 Hybrid 인덱싱"""
        from pathlib import Path

        docs = []
        metas = []
        ids = []

        for md_file in Path(dir_path).rglob("*.md"):
            with open(md_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

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
    """텍스트를 청크로 분할"""
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
