"""LLM Provider abstraction layer.

Supports DeepSeek via OpenAI-compatible API.
Easy to swap to other providers (Qwen, GLM, etc.) by changing config.
"""

from langchain_openai import ChatOpenAI

from app.core.config import settings


def get_llm() -> ChatOpenAI:
    """Create and return the LLM instance."""
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.deepseek_api_key,
        openai_api_base=settings.deepseek_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


def get_result_interpreter() -> ChatOpenAI:
    """A separate LLM instance with higher temperature for natural language responses."""
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.deepseek_api_key,
        openai_api_base=settings.deepseek_base_url,
        temperature=0.7,
        max_tokens=2048,
    )
