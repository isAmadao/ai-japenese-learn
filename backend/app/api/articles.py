"""Article API endpoints — generate and retrieve articles."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.article import (
    ArticleGenerateRequest,
    ArticleGenerateResponse,
    ArticleResponse,
)
from app.services.article_service import article_service

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.post("/generate", response_model=ArticleGenerateResponse)
def generate_article(
    request: ArticleGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a short essay using selected vocabulary at a specified level."""
    if not request.word_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个单词")
    if request.level not in ("N5", "N4", "N3", "N2", "N1"):
        raise HTTPException(status_code=400, detail="级别无效，请选择 N5-N1")

    try:
        article = article_service.generate_article(
            db, request.word_ids, request.level
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not article:
        raise HTTPException(status_code=404, detail="未找到指定的单词")

    words_data = [
        {"id": w.id, "japanese": w.japanese, "kana": w.kana, "chinese_meaning": w.chinese_meaning}
        for w in article.words
    ]
    article_resp = ArticleResponse(
        id=article.id,
        title=article.title,
        content_japanese=article.content_japanese,
        content_chinese=article.content_chinese,
        level=article.level,
        created_at=article.created_at.isoformat() if article.created_at else None,
        words=words_data,
    )
    return ArticleGenerateResponse(article=article_resp)


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Get article details by ID."""
    article = article_service.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章未找到")

    words_data = [
        {"id": w.id, "japanese": w.japanese, "kana": w.kana, "chinese_meaning": w.chinese_meaning}
        for w in article.words
    ]
    return ArticleResponse(
        id=article.id,
        title=article.title,
        content_japanese=article.content_japanese,
        content_chinese=article.content_chinese,
        level=article.level,
        created_at=article.created_at.isoformat() if article.created_at else None,
        words=words_data,
    )
