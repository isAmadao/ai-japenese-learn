"""Word service — data-flow v2.

Only favorited words persist to DB.  "换一批" stores results in Redis (session-scoped).
Browser refresh reuses cached session words instead of generating new ones.
"""

import json
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.word import Word
from app.models.favorite import Favorite
from app.models.article import Article, article_words
from app.agent.word_agent import word_agent
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

# Redis key prefix for session-cached words
_SESSION_CACHE_PREFIX = "session_words:"

# ── helpers ────────────────────────────────────────────────

def _session_cache_key(session_id: str) -> str:
    return f"{_SESSION_CACHE_PREFIX}{session_id}"


def _map_llm_word(wd: dict, idx: int) -> dict:
    """Normalise LLM output to CachedWord format.

    The agent may return legacy keys (japanese / chinese_meaning) or
    new keys (name / translation).  Handle both gracefully.
    """
    return {
        "id": idx,
        "name": wd.get("name") or wd.get("japanese", ""),
        "kana": wd.get("kana", ""),
        "translation": wd.get("translation") or wd.get("chinese_meaning", ""),
        "description": wd.get("description"),
        "type": wd.get("type"),
        "example_sentences": wd.get("example_sentences", []),
    }


# ── Service ────────────────────────────────────────────────

class WordService:
    """Word operations — session-cached generation + on-favorite persistence."""

    USER_ID = "default"

    # ═══════════════════════════════════════════════════════
    #  "换一批" — generate → Redis cache (no DB write)
    # ═══════════════════════════════════════════════════════

    def get_random_words(
        self, db: Session, count: int = 5,
        session_id: Optional[str] = None,
    ) -> list[dict]:
        """Return random words for the current session.

        Flow:
          1. Check Redis for cached session words (browser refresh reuses these)
          2. If miss → query DB for already-favorited names → call LLM →
             cache in Redis → return
          3. Never writes to DB (only Redis)
        """
        sid = session_id or "default"

        # ── 1. Check Redis session cache ────────────────
        cached = redis_client._sync_get(_session_cache_key(sid))
        if cached is not None:
            try:
                words = json.loads(cached)
                logger.info(f"[Session cache HIT] {sid} — {len(words)} words")
                return words[:count]
            except (json.JSONDecodeError, TypeError):
                pass

        # ── 2. Query DB for already-favorited names ─────
        favorited_names = {
            w.name for w in db.query(Word.name).all()
        }
        logger.info(f"[Session cache MISS] {sid} — known words: {len(favorited_names)}")

        # ── 3. Generate via LLM (no Redis cache, each batch is new) ──
        try:
            new_words_data = word_agent.generate_words(
                count=count + 2,
                exclude=list(favorited_names) if favorited_names else None,
                use_cache=False,
            )
        except Exception as e:
            raise RuntimeError(f"词汇生成失败: {e}")

        # ── 4. Format & save to Redis session cache ─────
        result = []
        seen = set(favorited_names)
        for wd in new_words_data:
            name = wd.get("name") or wd.get("japanese", "")
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(_map_llm_word(wd, len(result) + 1))
            if len(result) >= count:
                break

        if not result:
            raise RuntimeError("词汇生成失败: LLM 返回空结果")

        # TTL = 1 hour; on browser refresh within the hour the same words show
        redis_client._sync_set(
            _session_cache_key(sid),
            json.dumps(result, ensure_ascii=False),
            ttl=3600,
        )

        return result[:count]

    # ═══════════════════════════════════════════════════════
    #  Favorite — persist to DB (Word + Favorite tables)
    # ═══════════════════════════════════════════════════════

    def toggle_favorite(
        self, db: Session, word_id: int,
        ext: Optional[dict] = None,
    ) -> dict:
        """Toggle favorite status for a cached word.

        On first-time favorite:
          1. Check if Word already exists by id (may have been cached)
          2. Create Word record with available data
          3. Create Favorite record
        """
        # Word_id here is the session-relative id (1-5), not a DB primary key.
        # We look up by a combination or create a new record.
        # For simplicity, we use a transient approach: the frontend sends the
        # full word data as ext when favoriting.
        fav = (
            db.query(Favorite)
            .filter(
                Favorite.word_id == word_id,
                Favorite.user_id == self.USER_ID,
            )
            .first()
        )

        if fav:
            # Unfavorite
            db.delete(fav)
            db.commit()
            return {"is_favorited": False, "message": "已取消收藏"}
        else:
            # Favorite — ensure Word record exists
            word = db.query(Word).filter(Word.id == word_id).first()
            if not word:
                # Ext contains the cached word data; create DB record
                word = Word(
                    id=word_id,
                    name=(ext or {}).get("name", ""),
                    kana=(ext or {}).get("kana", ""),
                    translation=(ext or {}).get("translation", ""),
                    description=(ext or {}).get("description"),
                    type=(ext or {}).get("type"),
                    example_sentences=(ext or {}).get("example_sentences"),
                    ext=ext,
                )
                db.add(word)
                db.flush()

            db.add(Favorite(word_id=word.id, user_id=self.USER_ID))
            db.commit()
            return {"is_favorited": True, "message": "收藏成功"}

    # ═══════════════════════════════════════════════════════
    #  Word detail (from DB, for favorited words)
    # ═══════════════════════════════════════════════════════

    def get_word_detail(self, db: Session, word_id: int) -> Optional[dict]:
        word = db.query(Word).filter(Word.id == word_id).first()
        if not word:
            return None

        fav = (
            db.query(Favorite)
            .filter(Favorite.word_id == word_id, Favorite.user_id == self.USER_ID)
            .first()
        )
        articles = (
            db.query(Article)
            .join(article_words, Article.id == article_words.c.article_id)
            .filter(article_words.c.word_id == word_id)
            .all()
        )

        result = word.to_dict()
        result["is_favorited"] = fav is not None
        result["favorited_at"] = fav.created_at.isoformat() if fav and fav.created_at else None
        result["articles"] = [{"id": a.id, "title": a.title, "level": a.level} for a in articles]
        return result

    # ═══════════════════════════════════════════════════════
    #  Favorites list (paginated)
    # ═══════════════════════════════════════════════════════

    def get_favorites_paginated(self, db: Session, page: int = 1, page_size: int = 30) -> dict:
        query = (
            db.query(Favorite)
            .filter(Favorite.user_id == self.USER_ID)
            .order_by(Favorite.created_at.desc())
        )
        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        favorites = query.offset((page - 1) * page_size).limit(page_size).all()

        words = [fav.word.to_dict() for fav in favorites if fav.word]
        return {
            "words": words,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


word_service = WordService()
