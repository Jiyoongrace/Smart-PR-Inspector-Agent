"""
Redis 캐시 유틸리티
분석 결과 및 중복 요청 방지 캐싱
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Redis 클라이언트 (지연 초기화)
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception as e:
            logger.warning(f"Redis 연결 실패, 메모리 캐시로 폴백: {e}")
            _redis_client = _MemoryCache()
    return _redis_client


async def get_cache(key: str) -> Optional[str]:
    """캐시에서 값 조회"""
    try:
        client = _get_redis()
        return await client.get(key)
    except Exception as e:
        logger.debug(f"캐시 조회 실패: {e}")
        return None


async def set_cache(key: str, value: str, ttl: int = 3600) -> bool:
    """캐시에 값 저장"""
    try:
        client = _get_redis()
        await client.setex(key, ttl, value)
        return True
    except Exception as e:
        logger.debug(f"캐시 저장 실패: {e}")
        return False


async def delete_cache(key: str) -> bool:
    """캐시에서 값 삭제"""
    try:
        client = _get_redis()
        await client.delete(key)
        return True
    except Exception as e:
        logger.debug(f"캐시 삭제 실패: {e}")
        return False


class _MemoryCache:
    """Redis 미사용 시 인메모리 폴백 캐시"""

    def __init__(self):
        self._store: dict = {}
        self._expiry: dict = {}

    async def get(self, key: str) -> Optional[str]:
        import time
        if key in self._expiry and time.time() > self._expiry[key]:
            del self._store[key]
            del self._expiry[key]
            return None
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        import time
        self._store[key] = value
        self._expiry[key] = time.time() + ttl

    async def delete(self, key: str):
        self._store.pop(key, None)
        self._expiry.pop(key, None)
