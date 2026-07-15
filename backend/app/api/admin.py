"""Admin API endpoints — business-specific (stats, words, articles).

User management endpoints are provided by the auth-kit (via ``auth_kit.initialize()``).
This file contains only the Japanese-learning-specific admin features.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.word import Word
from app.models.favorite import Favorite
from app.models.article import Article

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Schemas ─────────────────────────────────────────────────────

from pydantic import BaseModel


class AdminStatsResponse(BaseModel):
    total_users: int
    total_words: int
    total_favorites: int
    total_articles: int
    words_by_type: dict[str, int]


class AdminWordItem(BaseModel):
    id: int
    name: str
    kana: str
    translation: str
    type: Optional[str] = None
    favorite_count: int = 0
    created_at: Optional[str] = None


class AdminWordListResponse(BaseModel):
    words: list[AdminWordItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminArticleItem(BaseModel):
    id: int
    title: str
    level: str
    word_count: int = 0
    created_at: Optional[str] = None


class AdminArticleListResponse(BaseModel):
    articles: list[AdminArticleItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Return overall platform statistics for the admin dashboard."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_words = db.query(func.count(Word.id)).scalar() or 0
    total_favorites = db.query(func.count(Favorite.id)).scalar() or 0
    total_articles = db.query(func.count(Article.id)).scalar() or 0

    rows = (
        db.query(Word.type, func.count(Word.id))
        .filter(Word.type.isnot(None))
        .group_by(Word.type)
        .all()
    )
    words_by_type: dict[str, int] = {}
    for t, cnt in rows:
        if t:
            words_by_type[t] = cnt

    return AdminStatsResponse(
        total_users=total_users,
        total_words=total_words,
        total_favorites=total_favorites,
        total_articles=total_articles,
        words_by_type=words_by_type,
    )


@router.get("/words", response_model=AdminWordListResponse)
def get_admin_words(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    type: str = Query(None, description="Filter by JLPT level (N5-N1)"),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Return paginated word list with favorite count."""
    query = db.query(Word)
    if type:
        query = query.filter(Word.type == type)

    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)

    words = (
        query.order_by(Word.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[AdminWordItem] = []
    for w in words:
        fav_count = (
            db.query(func.count(Favorite.id))
            .filter(Favorite.word_id == w.id)
            .scalar() or 0
        )
        items.append(
            AdminWordItem(
                id=w.id,
                name=w.name,
                kana=w.kana,
                translation=w.translation,
                type=w.type,
                favorite_count=fav_count,
                created_at=w.created_at.isoformat() if w.created_at else None,
            )
        )

    return AdminWordListResponse(
        words=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/articles", response_model=AdminArticleListResponse)
def get_admin_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Return paginated article list."""
    total = db.query(func.count(Article.id)).scalar() or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    articles = (
        db.query(Article)
        .order_by(Article.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[AdminArticleItem] = []
    for a in articles:
        items.append(
            AdminArticleItem(
                id=a.id,
                title=a.title,
                level=a.level,
                word_count=len(a.words) if a.words else 0,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
        )

    return AdminArticleListResponse(
        articles=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
