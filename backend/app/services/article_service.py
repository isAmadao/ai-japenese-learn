"""Article service — generation and management of short essays."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.word import Word
from app.models.article import Article, article_words
from app.services.llm_service import llm_service


class ArticleService:
    """Handles article generation using LLM and article CRUD."""

    def generate_article(
        self, db: Session, word_ids: list[int], level: str
    ) -> Optional[Article]:
        """Generate an article using selected vocabulary words at a given level."""
        words = (
            db.query(Word).filter(Word.id.in_(word_ids)).all()
        )
        if not words:
            return None

        word_dicts = [w.to_dict() for w in words]

        try:
            result = llm_service.generate_article(word_dicts, level)
        except Exception as e:
            raise RuntimeError(f"Article generation failed: {e}")

        if not result or not result.get("title"):
            raise RuntimeError("LLM returned incomplete article")

        article = Article(
            title=result["title"],
            content_japanese=result.get("content_japanese", ""),
            content_chinese=result.get("content_chinese", ""),
            level=level,
        )
        db.add(article)
        db.flush()

        # Associate article with words
        for word in words:
            db.execute(
                article_words.insert().values(
                    article_id=article.id,
                    word_id=word.id,
                )
            )

        db.commit()
        db.refresh(article)
        return article

    def get_article(self, db: Session, article_id: int) -> Optional[Article]:
        """Get article by ID with word associations."""
        return db.query(Article).filter(Article.id == article_id).first()


article_service = ArticleService()
