"""
PR 분석 이력 SQLite 영속화
SQLAlchemy ORM 기반 동기 DB 접근 (asyncio.to_thread로 비동기 래핑)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

# SQLite 기본 사용, PostgreSQL은 psycopg2 설치된 경우에만
def _resolve_db_url() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite:///./pr_inspector.db")
    if "postgresql" in raw or "postgres" in raw:
        try:
            import psycopg2  # noqa: F401
            # asyncpg → psycopg2 드라이버로 변환
            return raw.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")
        except ImportError:
            logger.warning("psycopg2 미설치 → SQLite로 폴백 (pip install psycopg2-binary 로 PostgreSQL 활성화)")
    return "sqlite:///./pr_inspector.db"


DATABASE_URL = _resolve_db_url()
_connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class PRAnalysisRecord(Base):
    """PR 분석 결과 이력 테이블"""
    __tablename__ = "pr_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(String(300), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    pr_title = Column(String(500), default="")
    pr_author = Column(String(100), default="")
    pr_url = Column(String(500), default="")
    base_branch = Column(String(100), default="main")
    head_branch = Column(String(100), default="")
    changed_files_count = Column(Integer, default=0)

    # 분석 결과 요약
    risk_level = Column(String(20), default="low")
    convention_passed = Column(Boolean, default=True)
    convention_violations = Column(Integer, default=0)
    test_passed = Column(Boolean, default=False)
    test_total = Column(Integer, default=0)
    test_passed_count = Column(Integer, default=0)
    has_api_changes = Column(Boolean, default=False)

    # 전체 분석 결과 JSON
    analysis_json = Column(Text, nullable=False, default="{}")

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    duration_seconds = Column(Float, default=0.0)


def init_db() -> None:
    """테이블 생성 (없으면 생성, 있으면 스킵)"""
    Base.metadata.create_all(engine)


def save_analysis(state_dict: Dict[str, Any]) -> int:
    """
    AgentState dict를 DB에 저장하고 record id 반환
    orchestrator의 stream complete 이벤트 이후 호출
    """
    init_db()

    pr = state_dict.get("pr_data") or {}
    convention = state_dict.get("convention_result") or {}
    test = state_dict.get("test_result") or {}
    impact = state_dict.get("impact_analysis") or {}

    record = PRAnalysisRecord(
        repo=pr.get("repo", ""),
        pr_number=pr.get("pr_number", 0),
        pr_title=pr.get("title", ""),
        pr_author=pr.get("author", ""),
        pr_url=pr.get("pr_url", ""),
        base_branch=pr.get("base_branch", "main"),
        head_branch=pr.get("head_branch", ""),
        changed_files_count=len(pr.get("changed_files", [])),
        risk_level=impact.get("risk_level", "low"),
        convention_passed=bool(convention.get("passed", True)),
        convention_violations=len(convention.get("violations", [])),
        test_passed=bool(test.get("passed", False)),
        test_total=test.get("total_tests", 0),
        test_passed_count=test.get("passed_tests", 0),
        has_api_changes=bool(impact.get("has_api_changes", False)),
        analysis_json=json.dumps(state_dict, ensure_ascii=False, default=str),
        created_at=datetime.utcnow(),
    )

    with SessionLocal() as session:
        session.add(record)
        session.commit()
        record_id = record.id
        logger.info(f"분석 결과 DB 저장 완료 (id={record_id}, PR #{pr.get('pr_number')})")
        return record_id


def list_analyses(limit: int = 50) -> List[Dict[str, Any]]:
    """최근 분석 이력 목록 반환 (분석 JSON 제외)"""
    init_db()
    with SessionLocal() as session:
        records = (
            session.query(PRAnalysisRecord)
            .order_by(PRAnalysisRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_to_summary(r) for r in records]


def get_analysis_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    """id로 분석 결과 상세 조회"""
    init_db()
    with SessionLocal() as session:
        record = session.get(PRAnalysisRecord, record_id)
        if not record:
            return None
        result = _to_summary(record)
        result["analysis"] = json.loads(record.analysis_json)
        return result


def get_analysis_by_pr(repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
    """레포+PR번호로 최신 분석 결과 조회"""
    init_db()
    with SessionLocal() as session:
        record = (
            session.query(PRAnalysisRecord)
            .filter(
                PRAnalysisRecord.repo == repo,
                PRAnalysisRecord.pr_number == pr_number,
            )
            .order_by(PRAnalysisRecord.created_at.desc())
            .first()
        )
        if not record:
            return None
        result = _to_summary(record)
        result["analysis"] = json.loads(record.analysis_json)
        return result


def _to_summary(record: PRAnalysisRecord) -> Dict[str, Any]:
    """PRAnalysisRecord → 요약 dict 변환"""
    return {
        "id": record.id,
        "repo": record.repo,
        "pr_number": record.pr_number,
        "pr_title": record.pr_title,
        "pr_author": record.pr_author,
        "pr_url": record.pr_url,
        "base_branch": record.base_branch,
        "head_branch": record.head_branch,
        "changed_files_count": record.changed_files_count,
        "risk_level": record.risk_level,
        "convention_passed": record.convention_passed,
        "convention_violations": record.convention_violations,
        "test_passed": record.test_passed,
        "test_total": record.test_total,
        "test_passed_count": record.test_passed_count,
        "has_api_changes": record.has_api_changes,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "duration_seconds": record.duration_seconds,
        "status": "completed",
    }
