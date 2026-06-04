"""WordAgent — generates Japanese vocabulary with Redis caching and Milvus vector storage.

Output fields (new LLM response format):
  name, kana, translation, description, type (N1-N5), example_sentences
"""

import json
import logging
from typing import Optional

from app.agent.base_agent import BaseAgent
from app.services.japanese_util import batch_verify_kana

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
          name, kana, translation, description, type, example_sentences
        """
        exclude_str = ""
        if exclude:
            exclude_str = f"请避免以下已存在的单词: {', '.join(exclude[:20])}"

        system_msg = "你是一位专业的日语教师。请始终用JSON格式回复。"
        user_prompt = f"""你是一位专业的日语教师。请生成 {count} 个常用的日语单词，用于日语学习应用。

每个单词必须包含以下字段（以JSON格式返回）：
- name: 日语表记（汉字/假名）
- kana: 假名读音（平假名）
- translation: 中文释义
- description: 简要用法说明或记忆提示（一两句话）
- type: 难度级别，从 N5（最简单）到 N1（最困难）
- example_sentences: 3个例句数组，每个例句包含 {{"japanese": "日语句子", "chinese": "中文翻译"}}

要求：
1. 单词覆盖不同词性（名词、动词、形容词、副词等）
2. 难度覆盖N5-N1，每批至少包含2个不同级别
3. 例句实用自然，能体现单词的典型用法
4. description 给出简短记忆技巧或区别说明
{exclude_str}

请直接返回JSON数组，格式：
[{{"name":"言葉","kana":"ことば","translation":"语言/单词","description":"指广义的语言或话语","type":"N5","example_sentences":[{{"japanese":"...","chinese":"..."}}]}}]
"""

        raw = self._generate(system_msg, user_prompt, use_cache=use_cache, cache_ttl=3600)

        try:
            result = self._extract_json(raw)
            if isinstance(result, dict) and "words" in result:
                result = result["words"]
            if isinstance(result, list):
                # Verify/correct kana via MeCab before returning
                result = batch_verify_kana(result)
                return result[:count]
            return [result]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse word list from LLM: {e}")

    def store_vector(self, word_id: int, word_dict: dict):
        """Generate embedding and store in Milvus."""
        text = (
            f"{word_dict.get('name', '')} "
            f"{word_dict.get('kana', '')} "
            f"{word_dict.get('translation', '')}"
        )
        self._embed_and_store(
            milvus_client.WORD_COLLECTION,
            text,
            {
                "id": word_id,
                "word_id": word_id,
                "name": word_dict.get("name", ""),
                "kana": word_dict.get("kana", ""),
                "translation": word_dict.get("translation", ""),
                "type": word_dict.get("type", ""),
            },
        )


from app.core.milvus_client import milvus_client  # noqa: E402

word_agent = WordAgent()
