"""LLM service — handles all interactions with Qwen via LangChain.

Generates:
- Random Japanese vocabulary words with examples
- Short essays at specified JLPT levels
- Future: skill-based language exercises
"""

import json
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings


class LLMService:
    """LangChain-powered service for Japanese language generation."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            temperature=0.8,
            max_tokens=4096,
        )

    def _extract_json(self, text: str) -> dict | list:
        """Extract JSON from LLM response, handling markdown fences and stray text."""
        # Try to find JSON within ```json ... ``` blocks
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1)
        # Also try to find the first `[` or `{` and last `]` or `}`
        text = text.strip()
        first = text.find("[")
        if first == -1:
            first = text.find("{")
        last = text.rfind("]")
        if last == -1 or last < first:
            last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first : last + 1]
        return json.loads(text)

    def generate_random_words(self, count: int = 5, exclude: Optional[list[str]] = None) -> list[dict]:
        """Generate random Japanese vocabulary words with example sentences.

        Returns a list of dicts with keys:
          japanese, kana, chinese_meaning, example_sentences
        """
        exclude_str = ""
        if exclude:
            exclude_str = f"请避免以下已存在的单词: {', '.join(exclude[:20])}"

        prompt = f"""你是一位专业的日语教师。请生成 {count} 个常用的日语单词，用于日语学习应用。

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

        messages = [
            SystemMessage(content="你是一位专业的日语教师，擅长生成教学材料。请始终用JSON格式回复。"),
            HumanMessage(content=prompt),
        ]

        response = self.llm.invoke(messages)
        try:
            result = self._extract_json(response.content)
            if isinstance(result, dict) and "words" in result:
                result = result["words"]
            if isinstance(result, list):
                return result[:count]
            return [result]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse LLM response: {e}\nResponse: {response.content[:500]}")

    def generate_article_stream(self, words: list[dict], level: str):
        """Stream article generation token by token (generator).

        Yields raw text chunks as they arrive from the LLM.
        The full accumulated text can be parsed as JSON at the end.
        """
        word_lines = "\n".join(
            f"- {w['japanese']}（{w.get('kana', '')}）: {w.get('chinese_meaning', '')}"
            for w in words
        )

        level_descriptions = {
            "N5": "使用最简单的句型和基础词汇，每句不超过10个词",
            "N4": "使用基本句型和常用词汇，句子结构简单清晰",
            "N3": "使用中等难度句型，适当使用连词使文章连贯",
            "N2": "使用较复杂的句型和表达，文章结构完整",
            "N1": "使用高级表达和复杂句型，接近母语者水平",
        }
        level_desc = level_descriptions.get(level, "使用中等难度句型")

        prompt = f"""你是一位专业的日语教师。请使用以下日语单词创作一篇短文，用于教学。

使用的单词：
{word_lines}

级别要求：{level} - {level_desc}

请返回JSON格式：
{{{{
    "title": "文章标题（日语）",
    "content_japanese": "日语正文（请自然融入所有指定单词，每个单词至少使用一次）",
    "content_chinese": "中文翻译（逐段对应日语正文）"
}}}}

要求：
1. 短文长度控制在200-400字（日语）
2. 确保所有给定单词都在文章中出现
3. 文章内容连贯、自然、有意义
4. 中文翻译准确，保持教学用途

请直接返回JSON（不要使用markdown代码块标记）。
"""

        messages = [
            SystemMessage(content="你是一位专业的日语教师，擅长生成教学用的日语短文。请始终用JSON格式回复。"),
            HumanMessage(content=prompt),
        ]

        for chunk in self.llm.stream(messages):
            content = chunk.content
            if content:
                yield content

    def generate_article(self, words: list[dict], level: str) -> dict:
        """Generate a short essay using given vocabulary at a specified JLPT level.

        Args:
            words: list of word dicts with japanese/kana/chinese_meaning keys
            level: N5 | N4 | N3 | N2 | N1

        Returns:
            dict with keys: title, content_japanese, content_chinese
        """
        word_lines = "\n".join(
            f"- {w['japanese']}（{w.get('kana', '')}）: {w.get('chinese_meaning', '')}"
            for w in words
        )

        level_descriptions = {
            "N5": "使用最简单的句型和基础词汇，每句不超过10个词",
            "N4": "使用基本句型和常用词汇，句子结构简单清晰",
            "N3": "使用中等难度句型，适当使用连词使文章连贯",
            "N2": "使用较复杂的句型和表达，文章结构完整",
            "N1": "使用高级表达和复杂句型，接近母语者水平",
        }
        level_desc = level_descriptions.get(level, "使用中等难度句型")

        prompt = f"""你是一位专业的日语教师。请使用以下日语单词创作一篇短文，用于教学。

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

        messages = [
            SystemMessage(content="你是一位专业的日语教师，擅长生成教学用的日语短文。请始终用JSON格式回复。"),
            HumanMessage(content=prompt),
        ]

        response = self.llm.invoke(messages)
        try:
            result = self._extract_json(response.content)
            if isinstance(result, list):
                result = result[0]
            return result
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse LLM response: {e}\nResponse: {response.content[:500]}")


llm_service = LLMService()
