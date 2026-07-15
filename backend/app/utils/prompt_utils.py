"""Prompt utilities — shared constants and helpers for LLM prompting."""

_CONTENT_TYPE_MAP = {
    "anime": "动漫",
    "drama": "日剧",
    "music": "歌曲/日语音乐",
    "daily": "日常生活",
    "": "",
}

_STYLE_HINTS = {
    "emotional": "感情丰富、打动人心",
    "funny": "搞笑轻松、幽默风趣",
    "adventure": "冒险刺激、充满想象力",
    "epic": "史诗感、宏大的叙事",
    "plain": "朴素真实、贴近日常生活",
    "suspense": "悬疑紧张、引人入胜",
    "sci-fi": "科幻未来感",
    "fantasy": "奇幻风格",
    "": "",
}


def build_style_instruction(
    content_type: str, style: str, source: str,
) -> str:
    """Build a prompt fragment describing the desired content type, style and source.

    If *source* is provided but the LLM doesn't know it, the instruction
    tells it to fall back to a general style rather than fabricating content.
    """
    parts = []
    if content_type:
        ct = _CONTENT_TYPE_MAP.get(content_type, content_type)
        if ct:
            parts.append(f"内容类型：以{ct}为背景或灵感")
    if style:
        st = _STYLE_HINTS.get(style, style)
        if st:
            parts.append(f"风格要求：{st}")
    if source:
        parts.append(
            f"参考来源：{source}。如果你了解这个作品/素材，请自然地引用其内容；"
            f"如果你不了解或不确定，不要硬编，按照你了解的内容类型和风格自由创作即可。"
        )
    return "\n".join(parts) + "\n" if parts else ""
