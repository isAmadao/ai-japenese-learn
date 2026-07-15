"""Shared test fixtures — in-memory SQLite database and API client.

All LLM / Redis / Milvus calls are mocked so tests are fast and hermetic.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

# ── In-memory SQLite engine (isolated per test session) ──────
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables once per test session."""
    import app.models.word      # noqa
    import app.models.favorite  # noqa
    import app.models.article   # noqa
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Yield a fresh DB session per test, rolled back after."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mock Redis calls to avoid needing a real Redis server.

    Uses a simple in-memory dict as the Redis stand-in.
    """
    import app.core.redis_client as rc

    _store: dict[str, str] = {}

    async def mock_connect(self):
        self._redis = _store  # type: ignore

    async def mock_disconnect(self):
        pass

    def mock_sync_get(_self, key: str):
        return _store.get(key)

    def mock_sync_set(_self, key: str, value: str, ttl: int = 3600):
        _store[key] = value

    monkeypatch.setattr(rc.RedisClient, "connect", mock_connect)
    monkeypatch.setattr(rc.RedisClient, "disconnect", mock_disconnect)
    monkeypatch.setattr(rc.RedisClient, "_sync_get", mock_sync_get)
    monkeypatch.setattr(rc.RedisClient, "_sync_set", mock_sync_set)


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Mock LLM calls to return a predictable word list."""
    import app.agent.base_agent as ba

    def mock_generate(self, system_msg, user_prompt, **kw):
        # Return a JSON array of fake words
        return json.dumps([
            {"name": "食べる", "kana": "たべる", "translation": "吃",
             "description": "一段动词", "type": "N5",
             "example_sentences": [{"japanese": "ご飯を食べる", "chinese": "吃饭"}]},
            {"name": "飲む", "kana": "のむ", "translation": "喝",
             "type": "N5",
             "example_sentences": [{"japanese": "水を飲む", "chinese": "喝水"}]},
            {"name": "寝る", "kana": "ねる", "translation": "睡觉",
             "type": "N5",
             "example_sentences": [{"japanese": "早く寝る", "chinese": "早点睡"}]},
            {"name": "見る", "kana": "みる", "translation": "看",
             "type": "N5",
             "example_sentences": [{"japanese": "テレビを見る", "chinese": "看电视"}]},
            {"name": "聞く", "kana": "きく", "translation": "听",
             "type": "N5",
             "example_sentences": [{"japanese": "音楽を聞く", "chinese": "听音乐"}]},
            {"name": "話す", "kana": "はなす", "translation": "说",
             "type": "N5",
             "example_sentences": [{"japanese": "日本語を話す", "chinese": "说日语"}]},
            {"name": "読む", "kana": "よむ", "translation": "读",
             "type": "N5",
             "example_sentences": [{"japanese": "本を読む", "chinese": "读书"}]},
        ])

    def mock_generate_stream(self, system_msg, user_prompt):
        yield json.dumps([
            {"name": "食べる", "kana": "たべる", "translation": "吃"},
            {"name": "飲む", "kana": "のむ", "translation": "喝"},
        ])

    monkeypatch.setattr(ba.BaseAgent, "_generate", mock_generate)
    monkeypatch.setattr(ba.BaseAgent, "_generate_stream", mock_generate_stream)


@pytest.fixture(autouse=True)
def mock_milvus(monkeypatch):
    """Mock Milvus to avoid needing a real server."""
    import app.core.milvus_client as mc

    def mock_setup(self):
        pass

    def mock_disconnect(self):
        pass

    monkeypatch.setattr(mc.MilvusClient, "setup", mock_setup)
    monkeypatch.setattr(mc.MilvusClient, "disconnect", mock_disconnect)


@pytest.fixture
def client(db):
    """FastAPI TestClient with overridden DB + auth dependencies."""
    from app.models.user import User
    from app.core.auth import get_current_user, require_admin

    fake_user = User(
        id=1, username="testuser", role="user",
        password_hash="", email="test@test.com",
    )
    fake_admin = User(
        id=2, username="admin", role="admin",
        password_hash="", email="admin@test.com",
    )

    def override_get_db():
        yield db

    async def override_get_current_user():
        return fake_user

    async def override_require_admin():
        return fake_admin

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_admin] = override_require_admin
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_word_data():
    """A minimal word dict for testing."""
    return {
        "name": "食べる",
        "kana": "たべる",
        "translation": "吃",
        "description": "一段动词，表示吃的行为",
        "type": "N5",
        "example_sentences": [
            {"japanese": "ご飯を食べる", "chinese": "吃饭"},
        ],
    }


@pytest.fixture
def another_word_data():
    """Another word for multi-word tests."""
    return {
        "name": "飲む",
        "kana": "のむ",
        "translation": "喝",
        "type": "N5",
        "example_sentences": [
            {"japanese": "水を飲む", "chinese": "喝水"},
        ],
    }
