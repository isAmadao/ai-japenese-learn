"""Word service — delegates to WordAgent, persists to DB + vector store, uses Redis cache."""

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.word import Word
from app.models.favorite import Favorite
from app.models.article import Article, article_words
from app.agent.word_agent import word_agent


class WordService:
    """Orchestrates word-related operations with Agent + DB + Vector store."""

    USER_ID = "default"

    # ── Random words (generate → save → vector) ─────────────

    def get_random_words(self, db: Session, count: int = 5) -> list[Word]:
        """Return *count* random words.

        Each call generates fresh words via the WordAgent (no Redis cache),
        persists them to DB + vector store, and excludes any words the
        user has already favorited.  This ensures "换一批" always returns
        genuinely new vocabulary.
        """
        # Collect Japanese texts to avoid re-generating known words
        all_known_japanese = set(
            w[0] for w in db.query(Word.japanese).all()
        )

        # Generate fresh words via agent (no cache — each call is new)
        try:
            new_words_data = word_agent.generate_words(
                count=count + 2,  # extra to allow for dedup
                exclude=list(all_known_japanese) if all_known_japanese else None,
                use_cache=False,
            )
        except Exception as e:
            # Fallback: return any non-favorited words from DB
            fallback = self._get_non_favorited(db, count)
            if fallback:
                return fallback
            raise RuntimeError(f"词汇生成失败: {e}")

        # Persist new words to DB + vector store
        saved_words = []
        seen = set(all_known_japanese)

        for wd in new_words_data:
            jp = wd.get("japanese", "").strip()
            if not jp or jp in seen:
                continue
            seen.add(jp)

            word = Word(
                japanese=jp,
                kana=wd.get("kana", ""),
                chinese_meaning=wd.get("chinese_meaning", ""),
                example_sentences=wd.get("example_sentences", []),
            )
            db.add(word)
            db.flush()

            # Store vector in Milvus (non-blocking on failure)
            word_agent.store_vector(word.id, wd)

            saved_words.append(word)

            if len(saved_words) >= count:
                break

        db.commit()
        return saved_words[:count]

    def _get_non_favorited(self, db: Session, count: int) -> list[Word]:
        """Fallback: return random non-favorited words from DB."""
        favorited_ids = [
            f[0]
            for f in db.query(Favorite.word_id)
            .filter(Favorite.user_id == self.USER_ID)
            .all()
        ]
        query = db.query(Word)
        if favorited_ids:
            query = query.filter(~Word.id.in_(favorited_ids))
        return query.order_by(func.random()).limit(count).all()

    # ── Word detail ─────────────────────────────────────────

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

    # ── Favorites ───────────────────────────────────────────

    def toggle_favorite(self, db: Session, word_id: int) -> dict:
        fav = (
            db.query(Favorite)
            .filter(Favorite.word_id == word_id, Favorite.user_id == self.USER_ID)
            .first()
        )
        if fav:
            db.delete(fav)
            db.commit()
            return {"is_favorited": False, "message": "已取消收藏"}
        else:
            db.add(Favorite(word_id=word_id, user_id=self.USER_ID))
            db.commit()
            return {"is_favorited": True, "message": "收藏成功"}

    def get_favorites_paginated(self, db: Session, page: int = 1, page_size: int = 30) -> dict:
        query = (
            db.query(Favorite)
            .filter(Favorite.user_id == self.USER_ID)
            .order_by(Favorite.created_at.desc())
        )
        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        favorites = query.offset((page - 1) * page_size).limit(page_size).all()

        words = []
        for fav in favorites:
            w = fav.word.to_dict() if fav.word else None
            if w:
                words.append(w)

        return {
            "words": words,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


word_service = WordService()
