"""Article model — stores generated short essays and their word associations."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.core.database import Base


# Association table: article <-> word (many-to-many)
article_words = Table(
    "article_words",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
    Column("word_id", Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False),
)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="文章标题")
    content_japanese = Column(Text, nullable=False, comment="日语正文")
    content_chinese = Column(Text, nullable=False, comment="中文翻译")
    level = Column(String(10), nullable=False, comment="级别 N5-N1")
    created_at = Column(DateTime, default=datetime.utcnow)

    words = relationship("Word", secondary=article_words, lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content_japanese": self.content_japanese,
            "content_chinese": self.content_chinese,
            "level": self.level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "words": [w.to_dict() for w in self.words] if self.words else [],
        }
