"""Base Agent — core LLM interaction, caching, and vector storage helpers."""

import hashlib
import json
import logging
from typing import Any, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.core.redis_client import redis_client
from app.core.milvus_client import milvus_client

logger = logging.getLogger(__name__)


class BaseAgent:
    """Foundation for all generation agents.

    Provides:
    - LLM invocation (with optional streaming)
    - Redis cache (avoid re-generating identical content)
    - Embedding generation + Milvus vector storage
    - JSON extraction from LLM responses
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 4096,
    ):
        self.llm = ChatOpenAI(
            model=model or settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._embeddings: Optional[OpenAIEmbeddings] = None

    # ── Embeddings (lazy init) ──────────────────────────────

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        if self._embeddings is None:
            self._embeddings = OpenAIEmbeddings(
                model=settings.LLM_EMBEDDING_MODEL,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_API_BASE,
            )
        return self._embeddings

    # ── LLM call with optional Redis cache ──────────────────

    def _make_cache_key(self, prefix: str, *parts: Any) -> str:
        """Deterministic cache key from prefix + parts."""
        raw = "|".join(str(p) for p in parts)
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"agent:{prefix}:{h}"

    def _generate(
        self,
        system_msg: str,
        user_prompt: str,
        use_cache: bool = True,
        cache_ttl: int = 3600,
    ) -> str:
        """Call LLM with caching.

        If a cached response exists for the same prompt, returns it directly.
        Otherwise calls the LLM, caches the result, and returns it.
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
        response = self.llm.invoke(messages)
        text = response.content or ""

        if use_cache and text:
            redis_client._sync_set(cache_key, text, ttl=cache_ttl)

        return text

    def _generate_stream(self, system_msg: str, user_prompt: str):
        """Call LLM in streaming mode (no caching for streams)."""
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_prompt),
        ]
        for chunk in self.llm.stream(messages):
            content = chunk.content
            if content:
                yield content

    # ── JSON extraction ─────────────────────────────────────

    def _extract_json(self, text: str):
        """Extract JSON object/array from LLM output."""
        import re
        text = text.strip()
        # Remove markdown fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1)
        # Find outermost { ... } or [ ... ]
        first = text.find("[")
        if first == -1:
            first = text.find("{")
        last = text.rfind("]")
        if last == -1 or last < first:
            last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first : last + 1]
        return json.loads(text)

    # ── Vector storage helpers ──────────────────────────────

    def _embed_and_store(
        self,
        collection_name: str,
        text: str,
        metadata: dict,
    ) -> bool:
        """Embed *text* and store the vector in Milvus.

        Returns True on success, False if Milvus is unavailable.
        """
        try:
            vector = self.embeddings.embed_query(text)
            milvus_client.insert(collection_name, vector, metadata)
            return True
        except Exception as e:
            logger.warning(f"Failed to store vector in Milvus: {e}")
            return False
