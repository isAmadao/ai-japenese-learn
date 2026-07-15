"""Learned words API — status machine: favorite → learned."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.word_service import word_service

router = APIRouter(prefix="/api/learned", tags=["learned"])


@router.get("")
def list_learned(
    type: str = Query(None, description="Filter by N5-N1"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated learned words, optionally filtered by type."""
    result = word_service.get_learned_words(
        db, user_id=str(current_user.id), type_filter=type, page=page, page_size=page_size,
    )
    return result


@router.get("/types")
def learned_type_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get count of learned words per type (N5-N1)."""
    return word_service.get_learned_type_counts(db, user_id=str(current_user.id))


@router.patch("/{word_id}/master")
def mark_as_mastered(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a learned word as mastered (learned → mastered).

    The user already knows this word well enough to move it to "mastered".
    """
    result = word_service.mark_as_mastered(db, word_id, user_id=str(current_user.id))
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result
