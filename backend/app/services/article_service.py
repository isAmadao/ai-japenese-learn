"""Article service — delegates to ArticleAgent, persists to DB + vector store, uses Redis cache."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.word import Word
from app.models.article import Article, article_words
from app.agent.article_agent import article_agent


class ArticleService:
    """Orchestrates article generation with Agent + DB + Vector store."""

    # ── Synchronous generation ────────────────────────────

    def generate_article(self, db: Session, word_ids: list[int], level: str) -> Optional[Article]:
        """Generate article via ArticleAgent, save to DB + vector store."""
        words = db.query(Word).filter(Word.id.in_(word_ids)).all()
        if not words:
            return None

        word_dicts = [w.to_dict() for w in words]

        try:
            # Agent handles LLM call + Redis cache
            result = article_agent.generate_article(word_dicts, level)
        except Exception as e:
            raise RuntimeError(f"Article generation failed: {e}")

        if not result or not result.get("title"):
            raise RuntimeError("LLM returned incomplete article")

        # Persist to DB
        article = Article(
            title=result["title"],
            content_japanese=result.get("content_japanese", ""),
            content_chinese=result.get("content_chinese", ""),
            level=level,
        )
        db.add(article)
        db.flush()

        for word in words:
            db.execute(
                article_words.insert().values(article_id=article.id, word_id=word.id)
            )

        db.commit()
        db.refresh(article)

        # Store vector in Milvus (non-blocking on failure)
        article_agent.store_vector(article.id, {
            "title": result["title"],
            "content_japanese": result.get("content_japanese", ""),
            "level": level,
        })

        return article

    # ── Get article ───────────────────────────────────────

    def get_article(self, db: Session, article_id: int) -> Optional[Article]:
        return db.query(Article).filter(Article.id == article_id).first()


article_service = ArticleService()
