"""Favorites API endpoints — paginated list."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.word import WordResponse, FavoriteListResponse
from app.services.word_service import word_service

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=FavoriteListResponse)
def list_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get paginated list of favorited words (5 rows × 6 cols = 30 per page)."""
    result = word_service.get_favorites_paginated(db, page=page, page_size=page_size)
    return FavoriteListResponse(**result)
