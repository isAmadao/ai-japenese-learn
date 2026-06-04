"""WordAgent — generates Japanese vocabulary with Redis caching and Milvus vector storage.

Flow:
  1. Check Redis cache for identical generation request
  2. If miss → call LLM → parse JSON → cache in Redis
  3. Return parsed word list; the caller (service) handles DB persistence
  4. Caller also triggers vector storage after DB save
"""

import json
import logging
from typing import Optional

from app.agent.base_agent import BaseAgent
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


class WordAgent(BaseAgent):
    """Agent responsible for generating Japanese vocabulary items."""

    def generate_words(
        self,
        count: int = 5,
        exclude: Optional[list[str]] = None,
        use_cache: bool = True,
    ) -> list[dict]:
        """Generate *count* random Japanese words.

        Returns a list of dicts with keys:
          japanese, kana, chinese_meaning, example_sentences
        """
        exclude_str = ""
        if exclude:
            exclude_str = f"请避免以下已存在的单词: {', '.join(exclude[:20])}"

        system_msg = "你是一位专业的日语教师。请始终用JSON格式回复。"
        user_prompt = f"""你是一位专业的日语教师。请生成 {count} 个常用的日语单词，用于日语学习应用。

每个单词必须包含以下字段（以JSON格式返回）：
- japanese: 日语表记（汉字/假名）
- kana: 假名读音（平假名）
- chinese_meaning: 中文释义
- example_sentences: 3个例句数组，每个例句包含 {{"japanese": "日语句子", "chinese": "中文翻译"}}

要求：
1. 单词覆盖不同词性（名词、动词、形容词等）
2. 难度在N5-N3之间，适合初中级学习者
3. 例句实用且自然，能体现单词的典型用法
4. 例句难度与单词级别匹配
{exclude_str}

请直接返回JSON数组（不要加markdown代码块标记，直接返回纯JSON），格式：
[{{"japanese":"言葉","kana":"ことば","chinese_meaning":"语言/单词","example_sentences":[{{"japanese":"...","chinese":"..."}}]}}]
"""

        raw = self._generate(system_msg, user_prompt, use_cache=use_cache, cache_ttl=3600)

        try:
            result = self._extract_json(raw)
            if isinstance(result, dict) and "words" in result:
                result = result["words"]
            if isinstance(result, list):
                return result[:count]
            return [result]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse word list from LLM: {e}")

    def store_vector(self, word_id: int, word_dict: dict):
        """Generate embedding and store in Milvus."""
        text = f"{word_dict['japanese']} {word_dict.get('kana', '')} {word_dict.get('chinese_meaning', '')}"
        self._embed_and_store(
            milvus_client.WORD_COLLECTION,  # type: ignore  (will be resolved at runtime)
            text,
            {
                "id": word_id,
                "word_id": word_id,
                "japanese": word_dict.get("japanese", ""),
                "kana": word_dict.get("kana", ""),
                "chinese_meaning": word_dict.get("chinese_meaning", ""),
            },
        )


from app.core.milvus_client import milvus_client  # noqa: E402

word_agent = WordAgent()
