"""WordAgent — generates Japanese vocabulary with Redis caching and Milvus vector storage.

Output fields (new LLM response format):
  name, kana, translation, description, type (N1-N5), example_sentences
"""

import json
import logging
import os
from typing import Optional, Generator

from app.agent.base_agent import BaseAgent
from app.agent.tool import make_tool
from app.services.japanese_util import batch_verify_kana, verify_kana
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)

# ── Dictionary lookup (lazy-loaded from JLPT JSON) ────────────

_DICT: dict[str, dict] | None = None


def _load_dict() -> dict[str, dict]:
    """Load JLPT dictionary into name → entry map (lazy, cached)."""
    global _DICT
    if _DICT is not None:
        return _DICT
    path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', 'core', 'dictionary', 'jlpt_words.json')
    )
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    _DICT = {}
    for entry in data:
        name = entry.get('name', '')
        if name:
            _DICT[name] = entry
    logger.info("[Dict] loaded %d entries from %s", len(_DICT), os.path.basename(path))
    return _DICT


def lookup_dictionary(word: str) -> dict | None:
    """Look up a word in the JLPT dictionary.

    Returns canonical entry (name, kana, translation, type, example_sentences)
    if found, None otherwise.
    """
    d = _load_dict()
    entry = d.get(word)
    if entry:
        return {
            "name": entry.get("name", word),
            "kana": entry.get("kana", ""),
            "translation": entry.get("translation", ""),
            "type": entry.get("type", ""),
            "example_sentences": entry.get("example_sentences", []),
        }
    return None


class WordAgent(BaseAgent):
    """Agent responsible for generating Japanese vocabulary items."""

    tools = [
        make_tool(
            verify_kana,
            name="verify_kana",
            description="验证并修正日语单词的假名读音。传入单词和 LLM 生成的读音，"
                        "返回修正后的正确读音。用于生成单词后校验读音准确性。",
            param_descriptions={
                "word": "日语单词（汉字/假名混写）",
                "llm_kana": "需要校验的假名读音",
            },
        ),
        make_tool(
            lookup_dictionary,
            name="lookup_dictionary",
            description="查询 JLPT 标准词汇表。传入日语单词，返回该词在标准词库中的"
                        "规范信息（读音、中文释义、级别）。如果单词不存在于标准词库中返回空。"
                        "用于生成新词后验证其规范性。",
            param_descriptions={
                "word": "日语单词（汉字/假名）",
            },
        ),
    ]

    def _cross_check_dict(self, word_obj: dict) -> dict:
        """Cross-check a generated word against the JLPT dictionary.

        If found in dictionary, prefer dictionary's kana/translation/type
        (more accurate than LLM output).  Otherwise keep LLM's version.
        """
        entry = self.run_tool("lookup_dictionary", word=word_obj.get("name", ""))
        if entry:
            for key in ("kana", "translation", "type"):
                if entry.get(key):
                    word_obj[key] = entry[key]
        return word_obj

    def generate_words(
        self,
        count: int = 5,
        exclude: Optional[list[str]] = None,
        use_cache: bool = True,
        api_key: Optional[str] = None,
    ) -> list[dict]:
        """Generate *count* random Japanese words.

        *api_key* overrides the instance/default API key for this call.
        Returns a list of dicts with keys:
          name, kana, translation, description, type, example_sentences
        """
        exclude_str = ""
        if exclude:
            exclude_str = f"请避免以下已存在的单词: {', '.join(exclude[:20])}"

        system_msg = "你是一位专业的日语教师。请始终用JSON格式回复。"
        user_prompt = self._build_prompt(count, exclude_str)
        raw = self._generate(system_msg, user_prompt, use_cache=use_cache, cache_ttl=3600, api_key=api_key)

        try:
            result = extract_json(raw)
            if isinstance(result, dict) and "words" in result:
                result = result["words"]
            if isinstance(result, list):
                # Verify kana + cross-check against dictionary
                result = batch_verify_kana(result)
                result = [self._cross_check_dict(w) for w in result]
                return result[:count]
            return [result]
        except (json.JSONDecodeError, KeyError) as e:
            # Retry once — LLM may have returned malformed JSON
            logger.warning("Word parse failed (attempt 1), retrying: %s", e)
            raw2 = self._generate(system_msg, user_prompt, use_cache=False, cache_ttl=3600)
            try:
                result2 = extract_json(raw2)
                if isinstance(result2, dict) and "words" in result2:
                    result2 = result2["words"]
                if isinstance(result2, list):
                    result2 = batch_verify_kana(result2)
                    result2 = [self._cross_check_dict(w) for w in result2]
                    return result2[:count]
                return [result2]
            except (json.JSONDecodeError, KeyError) as e2:
                raise RuntimeError(f"Failed to parse word list from LLM after retry: {e2}")

    def generate_words_stream(
        self,
        count: int = 5,
        exclude: Optional[list[str]] = None,
        api_key: Optional[str] = None,
    ) -> Generator[dict, None, None]:
        """Stream word generation — accumulate LLM tokens, then yield each word row.

        Uses LLM streaming to collect the response progressively. Once the
        stream completes, parses the full JSON and yields each word object
        individually.  This gives "row-level streaming": the frontend receives
        each word as a separate SSE event for progressive display.
        *api_key* overrides the instance/default API key for this call.
        """
        exclude_str = ""
        if exclude:
            exclude_str = f"请避免以下已存在的单词: {', '.join(exclude[:20])}"

        system_msg = "你是一位专业的日语教师。请始终用JSON格式回复。"
        user_prompt = self._build_prompt(count, exclude_str)

        buffer = ""
        for token in self._generate_stream(system_msg, user_prompt, api_key=api_key):
            buffer += token

        # Stream complete — parse the full JSON now
        try:
            data = extract_json(buffer)
        except Exception as e:
            logger.warning(f"Stream JSON parse failed (attempt 1), retrying: {e}")
            # Retry stream once
            buffer = ""
            for token in self._generate_stream(system_msg, user_prompt):
                buffer += token
            try:
                data = extract_json(buffer)
            except Exception as e2:
                logger.error(f"Stream JSON parse failed after retry: {e2}")
                return

        if isinstance(data, dict) and "words" in data:
            data = data["words"]

        if not isinstance(data, list):
            logger.error(f"generate_words_stream: unexpected type {type(data)}")
            return

        seen = set()
        for word_obj in data:
            if not isinstance(word_obj, dict):
                continue
            name = word_obj.get("name") or word_obj.get("japanese", "")
            if not name or name in seen:
                continue
            seen.add(name)
            corrected = self.run_tool(
                "verify_kana",
                word=word_obj.get("name", ""),
                llm_kana=word_obj.get("kana", ""),
            )
            if corrected:
                word_obj["kana"] = corrected
            word_obj = self._cross_check_dict(word_obj)
            yield word_obj
            if len(seen) >= count:
                return

    def _build_prompt(self, count: int, exclude_str: str = "") -> str:
        """Build the LLM prompt for word generation."""
        return f"""你是一位专业的日语教师。请生成 {count} 个常用的日语单词，用于日语学习应用。

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

    def enrich_sentences(
        self, name: str, kana: str, translation: str, type: str = "N5",
        api_key: Optional[str] = None,
        content_type: str = "",
        style: str = "",
        source: str = "",
    ) -> list[dict]:
        """Generate 3 new example sentences for an existing word via LLM.

        *content_type* — anime / drama / music / daily / ""
        *style* — emotional / funny / adventure / epic / plain / suspense / sci-fi / fantasy / ""
        *source* — specific anime / drama / song name (optional)
        *api_key* overrides the instance/default API key for this call.
        Returns a list of [{"japanese": "...", "chinese": "..."}].
        """
        # Build style instruction
        from app.utils.prompt_utils import build_style_instruction
        style_inst = build_style_instruction(content_type, style, source)

        system_msg = "你是一位专业的日语教师。请用JSON格式回复。"
        user_prompt = (
            f"为以下日语单词生成3个实用例句。\n\n"
            f"单词: {name}（{kana}）\n"
            f"中文释义: {translation}\n"
            f"难度: {type}\n\n"
            f"要求：\n"
            f"1. 句子难度与{type}级别匹配\n"
            f"2. 每个句子要用到该单词\n"
            f"3. 句子实用自然，覆盖不同场景\n"
            f"4. 不超过20词/句\n"
            f"{style_inst}"
            f"\n返回JSON格式：\n"
            f'[{{"japanese":"第一个日语句子","chinese":"中文翻译"}},...]'
        )

        raw = self._generate(system_msg, user_prompt, use_cache=False, api_key=api_key)
        try:
            data = extract_json(raw)
            if isinstance(data, list):
                # Validate each entry has required fields
                valid = []
                for s in data[:3]:
                    if isinstance(s, dict) and s.get("japanese") and s.get("chinese"):
                        valid.append(s)
                if valid:
                    return valid
            # Single sentence wrapped in dict
            if isinstance(data, dict) and data.get("japanese"):
                return [data]
        except Exception as e:
            logger.warning(f"enrich_sentences parse failed: {e}")

        # Final fallback: return empty
        return []

    def store_vector(self, word_id: int, word_dict: dict) -> bool:
        """Generate embedding and store in Milvus.

        Returns True on success, False on failure.
        """
        from app.services.vector_service import vector_service

        text = (
            f"{word_dict.get('name', '')} "
            f"{word_dict.get('kana', '')} "
            f"{word_dict.get('translation', '')}"
        )
        return vector_service.embed_and_store(
            "word_vectors",
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


word_agent = WordAgent()
