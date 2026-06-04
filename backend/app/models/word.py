"""Word model — stores Japanese vocabulary items."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, JSON, DateTime
from app.core.database import Base


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    japanese = Column(String(100), nullable=False, index=True, comment="日语表记")
    kana = Column(String(200), nullable=False, comment="假名读音")
    chinese_meaning = Column(String(300), nullable=False, comment="中文释义")
    example_sentences = Column(JSON, nullable=False, comment="例句 [{'japanese':'','chinese':''}]")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "japanese": self.japanese,
            "kana": self.kana,
            "chinese_meaning": self.chinese_meaning,
            "example_sentences": self.example_sentences or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
