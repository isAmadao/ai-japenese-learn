#!/usr/bin/env python3
"""Convert firavoyage Anki JLPT CSV to our dictionary JSON format.

Usage:
  python scripts/convert_anki_jlpt.py                  # uses local notes.csv
  python scripts/convert_anki_jlpt.py --download        # downloads from GitHub first

Source: https://github.com/firavoyage/_anki-jlpt-decks
License: CC-BY-NC-SA
"""

import csv
import json
import os
import re
import sys
import urllib.request

# ── Config ────────────────────────────────────────────────

CSV_URL = (
    "https://raw.githubusercontent.com/"
    "firavoyage/_anki-jlpt-decks/main/NEW-JLPT/notes.csv"
)
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dictionary", "notes.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dictionary", "jlpt_words.json")
CORE_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "core", "dictionary", "jlpt_words.json")

# CSV column indices (0-indexed)
COL_DECK = 0
COL_WORD = 2
COL_POS = 4
COL_READING = 5
COL_CN = 6        # Simplified Chinese translation
COL_EX_JP = 11    # Raw Japanese example sentence
COL_EX_CN = 13    # Simplified Chinese example translation
COL_TAGS = 38     # Tags column

# Parts of speech to include (N = noun, 動 = verb, 形 = adjective, 副 = adverb, etc.)
# Skip grammar patterns (接尾 = suffix, 接頭 = prefix, 助詞 = particle, etc.)
SKIP_POS = {"接尾", "接頭", "助詞", "助動", "連語", "感"}


def parse_level(deck: str) -> str:
    """Extract JLPT level from deck name like 'NEW-JLPT::NEW-N5'."""
    m = re.search(r"NEW-(N[1-5])", deck)
    return m.group(1) if m else "N5"


def clean(text: str) -> str:
    """Remove HTML tags and furigana annotations like [xxx]."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[[^\]]+\]", "", text)
    return text.strip()


def is_vocab(word: str, pos: str) -> bool:
    """Return True if this entry is a real vocabulary word (not grammar)."""
    word = word.strip()
    if not word:
        return False
    if word.startswith("〜") or word.startswith("～"):
        return False
    if pos.strip() in SKIP_POS:
        return False
    return True


def download_csv():
    """Download the Anki CSV if not present."""
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    if os.path.isfile(CSV_PATH):
        print(f"✓ Using existing: {CSV_PATH} ({os.path.getsize(CSV_PATH) // 1024} KB)")
        return
    print(f"Downloading {CSV_URL} ...")
    urllib.request.urlretrieve(CSV_URL, CSV_PATH)
    size = os.path.getsize(CSV_PATH) // 1024
    print(f"✓ Downloaded: {CSV_PATH} ({size} KB)")


def convert():
    """Convert Anki CSV to dictionary JSON."""
    download_csv()

    words = []
    seen = set()

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue

            # Pad short rows
            while len(row) < COL_TAGS + 1:
                row.append("")

            deck = row[COL_DECK]
            word = row[COL_WORD].strip()
            pos = row[COL_POS].strip()
            reading = row[COL_READING].strip()
            translation = clean(row[COL_CN])
            ex_jp_raw = row[COL_EX_JP].strip()
            ex_cn_raw = row[COL_EX_CN].strip()

            if not word or not reading or not translation:
                continue
            if not is_vocab(word, pos):
                continue
            if word in seen:
                continue
            seen.add(word)

            level = parse_level(deck)
            ex_jp = clean(ex_jp_raw)
            ex_cn = clean(ex_cn_raw)

            entry = {
                "name": word,
                "kana": reading,
                "translation": translation,
                "description": "",
                "type": level,
                "example_sentences": [],
            }

            if ex_jp and ex_cn:
                entry["example_sentences"].append({
                    "japanese": ex_jp,
                    "chinese": ex_cn,
                })

            words.append(entry)

    # Write output
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    # Also copy to app/core/dictionary/ for Docker
    os.makedirs(os.path.dirname(CORE_PATH), exist_ok=True)
    with open(CORE_PATH, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    # Stats
    levels = {}
    for w in words:
        lv = w["type"]
        levels[lv] = levels.get(lv, 0) + 1

    print(f"\n✅ 转换完成！共 {len(words)} 个词")
    print("  级别分布:")
    for k in sorted(levels.keys()):
        print(f"    {k}: {levels[k]}")
    print(f"\n  输出: {OUT_PATH}")
    print(f"  镜像: {CORE_PATH}")


if __name__ == "__main__":
    if "--download" in sys.argv:
        download_csv()
    else:
        convert()
