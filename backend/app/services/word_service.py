"""Word service — business logic for word management."""

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.word import Word
from app.models.favorite import Favorite
from app.models.article import Article, article_words
from app.services.llm_service import llm_service


class WordService:
    """Handles word generation, retrieval, and favorite management."""

    USER_ID = "default"

    def get_random_words(self, db: Session, count: int = 5) -> list[Word]:
        """Get random words not yet favorited by the user.
        If insufficient words exist, generate more via LLM.
        """
        favorited_ids = [
            f[0]
            for f in db.query(Favorite.word_id)
            .filter(Favorite.user_id == self.USER_ID)
            .all()
        ]

        # Try to get non-favorited words from database
        query = db.query(Word)
        if favorited_ids:
            query = query.filter(~Word.id.in_(favorited_ids))
        existing_words = query.order_by(func.random()).limit(count).all()

        # If we have enough, return them
        if len(existing_words) >= count:
            return existing_words[:count]

        # Need more — generate via LLM
        existing_japanese = set(w[0] for w in db.query(Word.japanese).all())
        needed = count - len(existing_words)

        try:
            new_words_data = llm_service.generate_random_words(
                count=needed + 2,  # Request extra for safety
                exclude=list(existing_japanese) if existing_japanese else None,
            )
        except Exception as e:
            # If LLM fails, return whatever we have
            return existing_words if existing_words else []

        # Save new words to database
        new_words = []
        for wd in new_words_data:
            jp = wd.get("japanese", "").strip()
            if not jp or jp in existing_japanese:
                continue
            existing_japanese.add(jp)

            word = Word(
                japanese=jp,
                kana=wd.get("kana", ""),
                chinese_meaning=wd.get("chinese_meaning", ""),
                example_sentences=wd.get("example_sentences", []),
            )
            db.add(word)
            db.flush()
            new_words.append(word)

        db.commit()
        return (existing_words + new_words)[:count]

    def get_word_detail(self, db: Session, word_id: int) -> Optional[dict]:
        """Get full word details including favorite status and related articles."""
        word = db.query(Word).filter(Word.id == word_id).first()
        if not word:
            return None

        fav = (
            db.query(Favorite)
            .filter(
                Favorite.word_id == word_id,
                Favorite.user_id == self.USER_ID,
            )
            .first()
        )

        # Find articles containing this word
        articles = (
            db.query(Article)
            .join(article_words, Article.id == article_words.c.article_id)
            .filter(article_words.c.word_id == word_id)
            .all()
        )

        result = word.to_dict()
        result["is_favorited"] = fav is not None
        result["favorited_at"] = fav.created_at.isoformat() if fav and fav.created_at else None
        result["articles"] = [
            {
                "id": a.id,
                "title": a.title,
                "level": a.level,
            }
            for a in articles
        ]
        return result

    def toggle_favorite(self, db: Session, word_id: int) -> dict:
        """Toggle favorite status for a word. Returns new status."""
        fav = (
            db.query(Favorite)
            .filter(
                Favorite.word_id == word_id,
                Favorite.user_id == self.USER_ID,
            )
            .first()
        )

        if fav:
            db.delete(fav)
            db.commit()
            return {"is_favorited": False, "message": "已取消收藏"}
        else:
            new_fav = Favorite(word_id=word_id, user_id=self.USER_ID)
            db.add(new_fav)
            db.commit()
            return {"is_favorited": True, "message": "收藏成功"}

    def get_favorites_paginated(
        self, db: Session, page: int = 1, page_size: int = 30
    ) -> dict:
        """Get paginated list of favorited words."""
        query = (
            db.query(Favorite)
            .filter(Favorite.user_id == self.USER_ID)
            .order_by(Favorite.created_at.desc())
        )

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)

        favorites = (
            query.offset((page - 1) * page_size).limit(page_size).all()
        )

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
