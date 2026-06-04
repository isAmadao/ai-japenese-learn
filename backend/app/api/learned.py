"""Learned words API — status machine: favorite → learned."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.word_service import word_service

router = APIRouter(prefix="/api/learned", tags=["learned"])


@router.get("")
def list_learned(
    type: str = Query(None, description="Filter by N5-N1"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get paginated learned words, optionally filtered by type."""
    result = word_service.get_learned_words(db, type_filter=type, page=page, page_size=page_size)
    return result


@router.get("/types")
def learned_type_counts(db: Session = Depends(get_db)):
    """Get count of learned words per type (N5-N1)."""
    return word_service.get_learned_type_counts(db)
