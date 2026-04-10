"""
LLM 클라이언트 헬퍼
OpenAI API를 중앙화하여 모든 노드에서 공통으로 사용
SKILL.md의 모델 설정을 참조하여 스킬별 적절한 모델 선택
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 기본 모델 (SKILL.md 로드 실패 시 폴백)
MODEL_FAST = "gpt-4o-mini"   # 컨벤션 체크, 도메인 설명, 문서 동기화 등 빠른 작업
MODEL_SMART = "gpt-4o-mini"  # 테스트 생성 등 품질이 중요한 작업


def call_llm(
    prompt: str,
    max_tokens: int = 1024,
    model: Optional[str] = None,
    system: Optional[str] = None,
) -> str:
    """
    OpenAI 호출 공통 함수

    Args:
        prompt: 사용자 프롬프트
        max_tokens: 최대 응답 토큰 수
        model: 사용할 모델 (기본값: gpt-4o-mini)
        system: 시스템 프롬프트 (선택)

    Returns:
        모델 응답 텍스트

    Raises:
        Exception: API 호출 실패 시
    """
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    selected_model = model or os.getenv("OPENAI_MODEL", MODEL_FAST)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3,
    )

    return response.choices[0].message.content.strip()


def call_llm_for_skill(
    skill_id: str,
    prompt: str,
    max_tokens: int = 1024,
    system: Optional[str] = None,
) -> str:
    """
    SKILL.md 기반 LLM 호출 — 스킬 ID에 맞는 모델을 자동 선택

    Args:
        skill_id: SKILL.md에 정의된 스킬 ID (예: "convention", "test_gen")
        prompt: 사용자 프롬프트
        max_tokens: 최대 응답 토큰 수
        system: 시스템 프롬프트 (선택)

    Returns:
        모델 응답 텍스트
    """
    try:
        from config.skills import get_skill_registry
        registry = get_skill_registry()
        model = registry.get_model_for_skill(skill_id)
    except Exception:
        model = None

    return call_llm(prompt, max_tokens=max_tokens, model=model, system=system)
