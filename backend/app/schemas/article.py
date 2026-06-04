"""Pydantic schemas for article-related API requests/responses."""

from typing import Optional

from pydantic import BaseModel


class ArticleWordBrief(BaseModel):
    id: int
    name: str
    kana: str
    translation: str
    type: Optional[str] = None

    class Config:
        from_attributes = True


class ArticleResponse(BaseModel):
    id: int
    title: str
    content_japanese: str
    content_chinese: str
    level: str
    created_at: Optional[str] = None
    words: list[ArticleWordBrief] = []

    class Config:
        from_attributes = True


class ArticleBrief(BaseModel):
    id: int
    title: str
    level: str

    class Config:
        from_attributes = True


class ArticleGenerateRequest(BaseModel):
    word_ids: list[int]
    level: str = "N5"


class ArticleGenerateResponse(BaseModel):
    article: ArticleResponse
