"""
팀 문서 업로드 → RAG 인덱싱 API
팀별 코드 컨벤션, 도메인 규칙 문서를 업로드하면
Hybrid RAG (Dense + Sparse + Re-ranking)에 인덱싱됩니다.

활용:
- convention 노드: 팀 컨벤션 문서를 RAG로 검색하여 LLM에 컨텍스트로 전달
- domain_explain 노드: 도메인 문서로 비즈니스 영향도 설명 생성
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from memory.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG"])

# 컨벤션 전용 벡터스토어 (도메인 문서와 분리)
_convention_store: Optional[VectorStore] = None


def get_convention_store() -> VectorStore:
    """팀 컨벤션 문서 전용 벡터스토어"""
    global _convention_store
    if _convention_store is None:
        _convention_store = VectorStore(collection_name="team_conventions")
    return _convention_store


@router.post("/upload/convention")
async def upload_convention_doc(
    file: UploadFile = File(...),
    team_name: str = "default",
):
    """
    팀 컨벤션 문서 업로드 → RAG 인덱싱

    Markdown 파일을 업로드하면 팀 컨벤션 벡터스토어에 인덱싱됩니다.
    컨벤션 검증 시 RAG로 검색하여 팀 고유 규칙을 LLM에 전달합니다.
    """
    if not file.filename.endswith((".md", ".txt", ".yaml", ".yml")):
        raise HTTPException(
            status_code=400,
            detail="지원 형식: .md, .txt, .yaml, .yml",
        )

    content = (await file.read()).decode("utf-8", errors="ignore")
    if not content.strip():
        raise HTTPException(status_code=400, detail="파일 내용이 비어있습니다")

    store = get_convention_store()

    # 청크 분할 후 인덱싱
    chunks = _chunk_text(content)
    ids = [f"conv_{team_name}_{file.filename}_{i}" for i in range(len(chunks))]
    metas = [
        {"source": file.filename, "team": team_name, "type": "convention", "chunk": i}
        for i in range(len(chunks))
    ]

    store.add_documents(chunks, metas, ids)

    logger.info(
        f"팀 컨벤션 문서 인덱싱 완료: {file.filename} "
        f"({len(chunks)}개 청크, 팀: {team_name})"
    )

    return {
        "status": "indexed",
        "filename": file.filename,
        "team": team_name,
        "chunks": len(chunks),
        "total_docs": store.count(),
    }


@router.post("/upload/domain")
async def upload_domain_doc(
    file: UploadFile = File(...),
    team_name: str = "default",
):
    """
    도메인 문서 업로드 → RAG 인덱싱

    비즈니스 로직, 정책 문서를 업로드하면 도메인 벡터스토어에 인덱싱됩니다.
    domain_explain 노드에서 RAG로 검색하여 비즈니스 영향도를 설명합니다.
    """
    if not file.filename.endswith((".md", ".txt")):
        raise HTTPException(
            status_code=400,
            detail="지원 형식: .md, .txt",
        )

    content = (await file.read()).decode("utf-8", errors="ignore")
    if not content.strip():
        raise HTTPException(status_code=400, detail="파일 내용이 비어있습니다")

    store = get_vector_store()

    chunks = _chunk_text(content)
    ids = [f"domain_{team_name}_{file.filename}_{i}" for i in range(len(chunks))]
    metas = [
        {"source": file.filename, "team": team_name, "type": "domain", "chunk": i}
        for i in range(len(chunks))
    ]

    store.add_documents(chunks, metas, ids)

    logger.info(
        f"도메인 문서 인덱싱 완료: {file.filename} "
        f"({len(chunks)}개 청크, 팀: {team_name})"
    )

    return {
        "status": "indexed",
        "filename": file.filename,
        "team": team_name,
        "chunks": len(chunks),
        "total_docs": store.count(),
    }


@router.get("/stats")
async def rag_stats():
    """RAG 인덱스 통계 조회"""
    domain_store = get_vector_store()
    convention_store = get_convention_store()

    return {
        "domain_docs": domain_store.count(),
        "convention_docs": convention_store.count(),
        "hybrid_rag": {
            "dense": "ChromaDB (DefaultEmbeddingFunction)",
            "sparse": "BM25Okapi (rank-bm25)",
            "reranker": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "fusion": "Reciprocal Rank Fusion (k=60)",
        },
    }


def _chunk_text(text: str, chunk_size: int = 800) -> list[str]:
    """텍스트를 의미 단위로 분할 (헤딩 기반 + 크기 제한)"""
    import re

    # 마크다운 헤딩(## ) 기준으로 섹션 분리
    sections = re.split(r"\n(?=#{1,3}\s)", text)

    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 섹션이 chunk_size 이하면 그대로
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # 큰 섹션은 chunk_size로 분할
            for i in range(0, len(section), chunk_size):
                chunk = section[i:i + chunk_size].strip()
                if chunk:
                    chunks.append(chunk)

    return chunks
