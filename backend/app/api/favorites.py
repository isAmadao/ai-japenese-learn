"""Favorites API endpoints — paginated list + mark as learned."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.word import WordResponse, FavoriteListResponse
from app.services.word_service import word_service

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=FavoriteListResponse)
def list_favorites(
    type: str = Query(None, description="Filter by N5-N1"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated list of favorited words (status = favorite), optionally filtered by type."""
    result = word_service.get_favorites_paginated(
        db, user_id=str(current_user.id),
        page=page, page_size=page_size, type_filter=type,
    )
    return FavoriteListResponse(**result)


@router.patch("/{word_id}/learn")
def mark_as_learned(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a favorited word as learned (status machine: favorite → learned)."""
    result = word_service.mark_as_learned(db, word_id, user_id=str(current_user.id))
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result
