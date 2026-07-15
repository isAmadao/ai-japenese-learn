"""One-time script: tag all untagged dictionary words with scene labels.

Uses LLM (Qwen via DashScope) to classify each word into one or more
scene categories.  Run once after adding the `scene` column to the Word table.

Usage:
    conda activate ai-japanese-learn
    cd backend
    python scripts/tag_scenes.py
"""

import json
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.models.word import Word
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── Scene categories ──────────────────────────────────────
SCENES = ["日常生活", "工作", "商务", "影视剧", "动漫", "旅游"]

SCENE_PROMPT = f"""你是一个日语单词场景分类器。请为每个日语单词判断它最可能出现在以下哪个场景中：

场景列表（可选择多个，用逗号分隔）：
{', '.join(SCENES)}

规则：
- 每个单词必须至少选择 1 个场景，最多 3 个
- 如果不确定，选择最相关的 1-2 个
- 只返回场景名称，用逗号分隔（如：日常生活, 工作）
- 不要输出任何其他内容

请为以下单词分类："""

BATCH_SIZE = 200  # larger batches to speed up


def keyword_tag(word_name: str, translation: str) -> list[str] | None:
    """Quick keyword-based tagging before calling LLM."""
    text = f"{word_name} {translation}".lower()
    tags = set()

    # Work-related keywords
    if any(k in text for k in ["仕事", "会社", "社長", "社員", "課長", "部長",
                                "取引", "打ち合わせ", "出張", "資料", "会議",
                                "報告", "売上", "給料", "昇進", "就職",
                                "採用", "面接", "退職", "勤務", "職場",
                                "上司", "同僚", "部下", "仕事", "働く",
                                "营业", "经营", "管理"]):
        tags.add("工作")

    # Business keywords
    if any(k in text for k in ["契約", "取引", "ビジネス", "売買", "交渉",
                                "合意", "購買", "投資", "融資", "株",
                                "商談", "顧客", "仕入", "発注", "受注",
                                "請求", "支払", "決済", "見積", "入札",
                                "貿易", "輸出", "輸入", "市場", "経済",
                                "利润", "成本", "预算"]):
        tags.add("商务")
        tags.add("工作")

    # Travel keywords
    if any(k in text for k in ["旅行", "観光", "ホテル", "旅館", "空港",
                                "駅", "切符", "予約", "パスポート", "地図",
                                "案内", "乗車", "運転", "道路", "地図",
                                "ホーム", "改札", "乗換", "出国", "入国",
                                "旅游", "酒店", "机场", "车票"]):
        tags.add("旅游")

    # Anime keywords
    if any(k in text for k in ["アニメ", "漫画", "キャラ", "主人公",
                                "魔法", "変身", "冒険", "友情",
                                "戦闘", "必殺", "忍", "妖怪",
                                "勇者", "魔王", "呪術", "能力"]):
        tags.add("动漫")

    # Drama/movie keywords
    if any(k in text for k in ["ドラマ", "映画", "俳優", "女優", "監督",
                                "脚本", "撮影", "演技", "役者", "出演",
                                "剧本", "演员", "拍摄", "镜头"]):
        tags.add("影视剧")

    return list(tags) if tags else None


def classify_batch(client: OpenAI, words: list[Word]) -> list[list[str]]:
    """Classify a batch of words — keyword first, then LLM for the rest."""
    results = []
    llm_words = []
    llm_indices = []

    for i, w in enumerate(words):
        kw = keyword_tag(w.name, w.translation)
        if kw:
            results.append(kw)
        else:
            results.append(None)  # placeholder
            llm_words.append(w)
            llm_indices.append(i)

    if not llm_words:
        return results  # all keyword-matched

    # LLM classify the remaining words
    word_lines = "\n".join(
        f"{j+1}. {w.name}（{w.kana}）— {w.translation}"
        for j, w in enumerate(llm_words)
    )
    prompt = SCENE_PROMPT + "\n\n" + word_lines

    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一位日语单词场景分类专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.05,
            max_tokens=4096,
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"  LLM call failed: {e}")
        # Default unmatched words to 日常生活
        for idx in llm_indices:
            results[idx] = ["日常生活"]
        return results

    # Parse response
    llm_idx = 0
    for line in text.split("\n"):
        line = line.strip()
        if not line or not line[0].isdigit():
            continue
        content = line.split(". ", 1)[-1] if ". " in line else line
        # Split by Chinese comma or English comma
        tags = [s.strip() for s in re.split(r"[，,]", content) if s.strip() in SCENES]
        if not tags:
            tags = ["日常生活"]  # default
        # Find next placeholder
        while llm_idx < len(llm_indices) and results[llm_indices[llm_idx]] is not None:
            llm_idx += 1
        if llm_idx < len(llm_indices):
            results[llm_indices[llm_idx]] = tags
            llm_idx += 1

    # Default any remaining placeholders
    for idx in llm_indices:
        if results[idx] is None:
            results[idx] = ["日常生活"]

    return results


def main():
    logger.info("=" * 50)
    logger.info("场景标签打标脚本 (v2 — keyword + LLM 混合)")
    logger.info(f"模型: {settings.LLM_MODEL}")
    logger.info(f"场景: {', '.join(SCENES)}")
    logger.info("=" * 50)

    init_db()
    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
    )

    db = SessionLocal()
    try:
        untagged = db.query(Word).filter(Word.scene.is_(None)).all()
        total = len(untagged)
        logger.info(f"\n待标记单词: {total}")

        if total == 0:
            logger.info("✅ 所有单词都已标记！")
            return

        tagged_count = 0
        for start in range(0, total, BATCH_SIZE):
            batch = untagged[start : start + BATCH_SIZE]
            batch_num = start // BATCH_SIZE + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(
                f"\n--- 批次 {batch_num}/{total_batches} "
                f"({start + 1}-{min(start + BATCH_SIZE, total)}/{total}) ---"
            )

            scenes = classify_batch(client, batch)

            for word, word_scenes in zip(batch, scenes):
                word.scene = word_scenes

            db.commit()
            batch_tagged = sum(1 for s in scenes if s)
            tagged_count += batch_tagged
            logger.info(f"  本批: {batch_tagged}/{len(batch)} 打标")

            if start + BATCH_SIZE < total:
                time.sleep(1.5)

        logger.info(f"\n✅ 完成！共标记 {tagged_count}/{total} 个单词")
    finally:
        db.close()


if __name__ == "__main__":
    main()
