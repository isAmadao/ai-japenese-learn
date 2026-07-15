"""Base Agent — core LLM interaction, Redis caching, and tool registry."""

import hashlib
import logging
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.core.redis_client import redis_client
from app.agent.tool import AgentTool

logger = logging.getLogger(__name__)


class BaseAgent:
    """Foundation for all generation agents.

    Provides:
    - LLM invocation (with optional streaming)
    - Redis cache (avoid re-generating identical content)
    - Tool registry (agents declare tools, call them during generation)
    """

    # Subclasses override with their own tool list
    tools: list[AgentTool] = []

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 4096,
    ):
        self._model = model or settings.LLM_MODEL
        self._api_key = api_key or settings.LLM_API_KEY
        self._base_url = settings.LLM_API_BASE
        self._temperature = temperature
        self._max_tokens = max_tokens
        self.llm = self._build_llm()

    def _build_llm(self, api_key: Optional[str] = None) -> ChatOpenAI:
        """Build a ChatOpenAI instance, optionally with a per-call API key override."""
        return ChatOpenAI(
            model=self._model,
            api_key=api_key or self._api_key or settings.LLM_API_KEY,
            base_url=self._base_url,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

    def _get_llm(self, api_key: Optional[str] = None) -> ChatOpenAI:
        """Get an LLM instance. Returns the cached one unless a per-call key is provided."""
        if api_key:
            return self._build_llm(api_key)
        return self.llm

    # ── Cache key ───────────────────────────────────────────

    def _make_cache_key(self, prefix: str, *parts: Any) -> str:
        """Deterministic cache key from prefix + parts."""
        raw = "|".join(str(p) for p in parts)
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"agent:{prefix}:{h}"

    # ── Tool registry ───────────────────────────────────────

    def tool_specs_for_prompt(self) -> str:
        """Format all registered tools as a text block for LLM system prompts."""
        if not self.tools:
            return ""
        sections = []
        for tool in self.tools:
            sections.append(tool.format_for_prompt())
        return "可用工具：\n" + "\n---\n".join(sections)

    def run_tool(self, name: str, **kwargs) -> Any:
        """Execute a registered tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool(**kwargs)
        raise ValueError(f"Agent 未注册工具: {name}")

    # ── LLM invoke (blocking, with cache) ───────────────────

    def _generate(
        self,
        system_msg: str,
        user_prompt: str,
        use_cache: bool = True,
        cache_ttl: int = 3600,
        api_key: Optional[str] = None,
    ) -> str:
        """Call LLM with caching and automatic retry.

        If a cached response exists for the same prompt, returns it directly.
        Otherwise calls the LLM (with up to 2 retries), caches the result, and returns it.
        *api_key* overrides the instance/default API key for this call.
        """
        cache_key = self._make_cache_key("llm", system_msg, user_prompt)

        if use_cache:
            cached = redis_client._sync_get(cache_key)
            if cached is not None:
                logger.info(f"[Cache HIT] {cache_key}")
                return cached

        logger.info(f"[Cache MISS] calling LLM — {cache_key[:24]}...")
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_prompt),
        ]
        llm = self._get_llm(api_key)

        # Retry: 2 attempts, 1s/3s backoff, for transient network/API errors
        last_exc = None
        for attempt in range(1, 3):
            try:
                response = llm.invoke(messages)
                text = response.content or ""
                if text:
                    if use_cache and text:
                        redis_client._sync_set(cache_key, text, ttl=cache_ttl)
                    return text
                # Empty response — retry
                last_exc = RuntimeError("LLM returned empty response")
                logger.warning(
                    "LLM empty response attempt %d/2 — retrying", attempt,
                )
                if attempt < 2:
                    import time
                    time.sleep(3.0 if attempt == 1 else 1.0)
            except Exception as e:
                last_exc = e
                if attempt == 2:
                    raise
                delay = 1.0 if attempt == 1 else 3.0
                logger.warning(
                    "LLM call attempt %d/2 failed: %s — retry in %.1fs",
                    attempt, e, delay,
                )
                import time
                time.sleep(delay)

        raise last_exc or RuntimeError("LLM generation failed after retries")

    # ── LLM stream ──────────────────────────────────────────

    def _generate_stream(self, system_msg: str, user_prompt: str, api_key: Optional[str] = None):
        """Call LLM in streaming mode (no caching for streams).

        *api_key* overrides the instance/default API key for this call.
        """
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_prompt),
        ]
        llm = self._get_llm(api_key)
        for chunk in llm.stream(messages):
            content = chunk.content
            if content:
                yield content
