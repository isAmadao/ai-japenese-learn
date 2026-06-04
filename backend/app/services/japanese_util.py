"""Japanese language utilities — kana verification via MeCab (fugashi + unidic).

Corrects LLM-hallucinated readings (e.g. 妥協 → "だかい" → "ダキョウ").
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_tagger = None


def _get_tagger():
    global _tagger
    if _tagger is None:
        try:
            from fugashi import Tagger
            _tagger = Tagger("-Owakati")
            logger.info("fugashi MeCab tagger loaded")
        except Exception as e:
            logger.warning(f"fugashi unavailable: {e}")
    return _tagger


def _extract_kana(node) -> Optional[str]:
    """Extract kana reading from a MeCab node, handling both
    old-style comma-separated features and UnidicFeatures26 objects."""
    try:
        feat = node.feature
        if feat is None:
            return None

        # UnidicFeatures26 object (fugashi + unidic-lite)
        if hasattr(feat, "kana") and feat.kana and feat.kana != "*":
            return feat.kana
        if hasattr(feat, "lForm") and feat.lForm and feat.lForm != "*":
            return feat.lForm

        # Fallback: try parsing as comma-separated string
        if isinstance(feat, str):
            parts = feat.split(",")
            if len(parts) >= 10 and parts[9] and parts[9] != "*":
                return parts[9]
            if len(parts) >= 8 and parts[7] and parts[7] != "*":
                return parts[7]
    except Exception:
        pass
    return None


def verify_kana(word: str, llm_kana: str) -> str:
    """Verify and correct kana reading using MeCab.

    Returns MeCab's reading (katakana) if available, else the LLM's guess.

    Examples:
        verify_kana("妥協", "だかい") -> "ダキョウ"  (corrected)
        verify_kana("食べる", "たべる") -> "タベル"   (correct, but katakana)
    """
    tagger = _get_tagger()
    if tagger is None:
        return llm_kana

    try:
        for node in tagger(word):
            kana = _extract_kana(node)
            if kana:
                # Normalize katakana → hiragana (MeCab returns katakana)
                return "".join(chr(ord(c) - 96) if "ァ" <= c <= "ヴ" else c for c in kana)
    except Exception as e:
        logger.debug(f"MeCab lookup failed for '{word}': {e}")

    return llm_kana


def batch_verify_kana(words: list[dict]) -> list[dict]:
    """Verify kana for all words in a batch. Modifies dicts in-place."""
    changed = 0
    for w in words:
        name = w.get("name", "")
        kana = w.get("kana", "")
        if name and kana:
            corrected = verify_kana(name, kana)
            if corrected and corrected != kana:
                logger.info(f"Kana corrected: {name} {kana} → {corrected}")
                w["kana"] = corrected
                changed += 1
    if changed:
        logger.info(f"Corrected {changed}/{len(words)} kana readings")
    return words
