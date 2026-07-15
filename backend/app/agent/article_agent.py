"""ArticleAgent — generates short essays using ReAct planning + tools.

Flow:
  1. verify_kana tool — corrects word readings before generation
  2. Plan step — LLM plans title + paragraph structure (cached)
  3. Generate step — SSE streams the article following the plan
  4. Redis cache — caches generated result for reuse
"""

import logging
from typing import Optional

from app.agent.base_agent import BaseAgent
from app.agent.tool import make_tool
from app.core.redis_client import redis_client
from app.services.japanese_util import verify_kana
from app.utils.prompt_utils import build_style_instruction

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

    tools = [
        make_tool(
            verify_kana,
            name="verify_kana",
            description="验证并修正日语单词的假名读音。传入单词和 LLM 生成的读音，"
                        "返回修正后的正确读音。用于写文章前确认单词读音准确。",
            param_descriptions={
                "word": "日语单词（汉字/假名混写）",
                "llm_kana": "需要校验的假名读音",
            },
        ),
    ]

    def _plan_article(
        self, word_lines: str, level: str, level_desc: str,
        content_type: str = "", style: str = "", source: str = "",
        api_key: Optional[str] = None,
    ) -> dict:
        """Plan article structure before generation — produces title + paragraph outline.

        Uses a separate LLM call (cached) to decide the article's structure,
        then returns the plan dict so the main generation can follow it.
        """
        style_inst = build_style_instruction(content_type, style, source)

        system_msg = "你是一位专业的日语教师。请用JSON格式回复。"
        prompt = f"""请为以下日语单词规划一篇短文的结构，用于教学。

使用的单词：
{word_lines}

级别要求：{level} - {level_desc}
{style_inst}
请返回JSON格式：
{{{{
    "title": "文章标题（日语）",
    "structure": [
        {{"focus": ["单词1的name", "单词2的name"], "summary_cn": "本段中文大意"}},
        ...
    ]
}}}}

要求：
1. 标题紧扣单词内容，简洁有力
2. 每段聚焦1-3个单词，确保所有单词被分配
3. 段落数量2-3段
4. 每段 summary_cn 说明本段将如何组织这些单词
"""
        raw = self._generate(system_msg, prompt, cache_ttl=7200, api_key=api_key)
        from app.utils.json_utils import extract_json
        result = extract_json(raw)
        if isinstance(result, list):
            result = result[0]
        return result

    def _make_article_prompt(
        self, word_lines: str, level: str, level_desc: str,
        content_type: str = "", style: str = "", source: str = "",
        plan: Optional[dict] = None,
    ) -> tuple[str, str]:
        """Build system and user prompts for article generation.

        If *plan* is provided, it will be included as structural guidance.
        """
        style_inst = build_style_instruction(content_type, style, source)

        plan_block = ""
        if plan:
            title = plan.get("title", "")
            structure = plan.get("structure", [])
            para_lines = []
            for i, p in enumerate(structure, 1):
                words_str = "、".join(p.get("focus", []))
                summary = p.get("summary_cn", "")
                para_lines.append(f"  第{i}段（关键词：{words_str}）：{summary}")
            plan_block = (
                f"请按照以下规划创作：\n"
                f"标题：{title}\n"
                f"段落安排：\n" + "\n".join(para_lines) + "\n\n"
            )

        system_msg = "你是一位专业的日语教师，擅长生成教学用的日语短文。请始终用JSON格式回复。"
        user_prompt = f"""你是一位专业的日语教师。请使用以下日语单词创作一篇短文，用于教学。

使用的单词：
{word_lines}

级别要求：{level} - {level_desc}
{style_inst}{plan_block}请返回JSON格式：
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
        return system_msg, user_prompt

    def generate_article_stream(
        self, words: list[dict], level: str, api_key: Optional[str] = None,
        content_type: str = "", style: str = "", source: str = "",
    ):
        """Stream article generation token-by-token (caches result after stream completes).
        *content_type* — anime / drama / music / daily / ""
        *style* — emotional / funny / adventure / epic / plain / suspense / sci-fi / fantasy / ""
        *source* — specific anime / drama / song name (optional)
        *api_key* overrides the instance/default API key for this call.

        生成流程：
          1. 校验每个单词的读音（verify_kana 工具）
          2. 规划文章结构（标题 + 段落安排）
          3. 按照规划生成完整的日语短文（流式输出）
          4. 缓存结果
        """
        # ── 1. 校验读音 ────────────────────────────────
        verified = []
        for w in words:
            corrected = self.run_tool(
                "verify_kana",
                word=w.get("name", ""),
                llm_kana=w.get("kana", ""),
            )
            if corrected:
                w = dict(w, kana=corrected)
            verified.append(w)

        word_lines = "\n".join(
            f"- {w['name']}（{w.get('kana', '')}）: {w.get('translation', '')}"
            for w in verified
        )
        level_desc = _LEVEL_HINTS.get(level, "使用中等难度句型")

        # ── 2. 规划结构 ────────────────────────────────
        plan = self._plan_article(
            word_lines, level, level_desc,
            content_type, style, source,
            api_key=api_key,
        )
        logger.info(
            "[Plan] article planned — title=%s, %d paragraphs",
            plan.get("title", "?"), len(plan.get("structure", [])),
        )

        # ── 2b. 覆盖度检查 ──────────────────────────────
        all_names = {w["name"] for w in verified}
        covered = set()
        for p in plan.get("structure", []):
            for w_name in p.get("focus", []):
                covered.add(w_name)
        missing = all_names - covered
        if missing:
            logger.warning(
                "[Coverage] plan missed %d words: %s — appending to last paragraph",
                len(missing), missing,
            )
            if plan.get("structure"):
                plan["structure"][-1].setdefault("focus", []).extend(missing)
            else:
                plan["structure"] = [
                    {"focus": list(missing), "summary_cn": f"补充涵盖单词：{'、'.join(missing)}"}
                ]

        # ── 3. 按规划生成 ──────────────────────────────
        system_msg, user_prompt = self._make_article_prompt(
            word_lines, level, level_desc, content_type, style, source,
            plan=plan,
        )

        buffer = ""
        for chunk in self._generate_stream(system_msg, user_prompt, api_key=api_key):
            buffer += chunk
            yield chunk

        # After stream completes, cache the result for subsequent requests
        if buffer.strip():
            cache_key = self._make_cache_key("llm", system_msg, user_prompt)
            try:
                redis_client._sync_set(cache_key, buffer, ttl=7200)
                logger.info(
                    "[SSE] cached article result for subsequent sync requests "
                    "(%s…)", cache_key[:24]
                )
            except Exception:
                logger.warning("Failed to cache SSE article result")

        # ── 4. 覆盖率后检 ──────────────────────────────
        used = {w["name"] for w in verified if w["name"] in buffer}
        missing_after = all_names - used
        if missing_after:
            logger.warning(
                "[Coverage] article missing %d/%d words: %s",
                len(missing_after), len(all_names), missing_after,
            )
        else:
            logger.info("[Coverage] all %d words covered in article", len(all_names))

    def store_vector(self, article_id: int, article_dict: dict):
        """Generate embedding and store in Milvus."""
        from app.services.vector_service import vector_service

        text = f"{article_dict.get('title', '')} {article_dict.get('content_japanese', '')}"
        vector_service.embed_and_store(
            "article_vectors",
            text,
            {
                "id": article_id,
                "article_id": article_id,
                "title": article_dict.get("title", ""),
                "level": article_dict.get("level", ""),
            },
        )


article_agent = ArticleAgent()
