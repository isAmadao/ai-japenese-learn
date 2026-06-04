"""ArticleAgent — generates short essays with Redis caching and Milvus vector storage.

Flow:
  1. Build a deterministic cache key from the word IDs + level
  2. If cache hit → return cached JSON directly
  3. If miss → call LLM → parse → cache in Redis
  4. Return parsed article dict for the caller (service) to persist
  5. Caller triggers vector storage after DB save
"""

import json
import logging
from typing import Optional

from app.agent.base_agent import BaseAgent
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


_LEVEL_HINTS = {
    "N5": "使用最简单的句型和基础词汇，每句不超过10个词",
    "N4": "使用基本句型和常用词汇，句子结构简单清晰",
    "N3": "使用中等难度句型，适当使用连词使文章连贯",
    "N2": "使用较复杂的句型和表达，文章结构完整",
    "N1": "使用高级表达和复杂句型，接近母语者水平",
}


class ArticleAgent(BaseAgent):
    """Agent responsible for generating short Japanese essays from vocabulary."""

    def generate_article(
        self,
        words: list[dict],
        level: str,
        use_cache: bool = True,
    ) -> dict:
        """Generate a short essay using *words* at JLPT *level*.

        Returns dict with keys: title, content_japanese, content_chinese
        """
        word_lines = "\n".join(
            f"- {w['name']}（{w.get('kana', '')}）: {w.get('translation', '')}"
            for w in words
        )
        level_desc = _LEVEL_HINTS.get(level, "使用中等难度句型")

        # Build a cache key from the word texts + level so identical sets
        # of words at the same level are only generated once.
        word_signatures = sorted(w.get("name", "") for w in words)

        system_msg = "你是一位专业的日语教师，擅长生成教学用的日语短文。请始终用JSON格式回复。"
        user_prompt = f"""你是一位专业的日语教师。请使用以下日语单词创作一篇短文，用于教学。

使用的单词：
{word_lines}

级别要求：{level} - {level_desc}

请返回JSON格式：
{{
    "title": "文章标题（日语）",
    "content_japanese": "日语正文（请自然融入所有指定单词，每个单词至少使用一次）",
    "content_chinese": "中文翻译（逐段对应日语正文）"
}}

要求：
1. 短文长度控制在200-400字（日语）
2. 确保所有给定单词都在文章中出现
3. 文章内容连贯、自然、有意义
4. 中文翻译准确，保持教学用途

请直接返回JSON（不要使用markdown代码块标记）。
"""

        raw = self._generate(
            system_msg,
            user_prompt,
            use_cache=use_cache,
            cache_ttl=7200,
        )

        try:
            result = self._extract_json(raw)
            if isinstance(result, list):
                result = result[0]
            return result
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse article from LLM: {e}")

    def generate_article_stream(self, words: list[dict], level: str):
        """Stream article generation token-by-token (no caching for streams)."""
        word_lines = "\n".join(
            f"- {w['name']}（{w.get('kana', '')}）: {w.get('translation', '')}"
            for w in words
        )
        level_desc = _LEVEL_HINTS.get(level, "使用中等难度句型")

        system_msg = "你是一位专业的日语教师，擅长生成教学用的日语短文。请始终用JSON格式回复。"
        user_prompt = f"""你是一位专业的日语教师。请使用以下日语单词创作一篇短文，用于教学。

使用的单词：
{word_lines}

级别要求：{level} - {level_desc}

请返回JSON格式：
{{
    "title": "文章标题（日语）",
    "content_japanese": "日语正文（请自然融入所有指定单词，每个单词至少使用一次）",
    "content_chinese": "中文翻译（逐段对应日语正文）"
}}

要求：
1. 短文长度控制在200-400字（日语）
2. 确保所有给定单词都在文章中出现
3. 文章内容连贯、自然、有意义
4. 中文翻译准确，保持教学用途

请直接返回JSON（不要使用markdown代码块标记）。
"""

        yield from self._generate_stream(system_msg, user_prompt)

    def store_vector(self, article_id: int, article_dict: dict):
        """Generate embedding and store in Milvus."""
        text = f"{article_dict.get('title', '')} {article_dict.get('content_japanese', '')}"
        self._embed_and_store(
            milvus_client.ARTICLE_COLLECTION,  # type: ignore
            text,
            {
                "id": article_id,
                "article_id": article_id,
                "title": article_dict.get("title", ""),
                "level": article_dict.get("level", ""),
            },
        )


from app.core.milvus_client import milvus_client  # noqa: E402

article_agent = ArticleAgent()
