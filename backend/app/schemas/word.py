"""Pydantic schemas for word-related API requests/responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ExampleSentence(BaseModel):
    japanese: str
    chinese: str


class WordResponse(BaseModel):
    id: int
    japanese: str
    kana: str
    chinese_meaning: str
    example_sentences: list[ExampleSentence]
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class WordDetailResponse(WordResponse):
    is_favorited: bool = False
    favorited_at: Optional[str] = None
    articles: list[dict] = []


class RandomWordsResponse(BaseModel):
    words: list[WordResponse]


class FavoriteToggleResponse(BaseModel):
    is_favorited: bool
    message: str


class FavoriteListResponse(BaseModel):
    words: list[WordResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
