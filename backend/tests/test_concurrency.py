"""Concurrency & race condition tests — standalone database.

Uses a file-based SQLite DB so each thread can have its own session
without interfering with the shared in-memory DB used by other tests.
"""

import os
import threading
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.word import Word
from app.models.favorite import Favorite
from app.services.word_service import word_service

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "test_concurrency.db")
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

# Enable WAL mode + increased timeout for better concurrent access
with engine.connect() as conn:
    conn.execute(sa_text("PRAGMA journal_mode=WAL"))
    conn.execute(sa_text("PRAGMA busy_timeout=5000"))
    conn.commit()
SessionFactory = sessionmaker(bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


@pytest.fixture
def session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionFactory(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


class TestConcurrentStateMachine:
    """Race conditions on the same word from multiple threads."""

    def _seed(self, session):
        """Ensure the test word exists with status=mastered."""
        word_service._save_words_as_mastered(session, [{
            "name": "競合", "kana": "きょうごう", "translation": "并发竞争",
        }])

    @pytest.mark.xfail(reason="SQLite 单写者限制，并发写入需 MySQL/PostgreSQL")
    def test_parallel_toggle_favorite(self, session):
        """多个线程切换同一个词的收藏状态，不应崩溃."""
        self._seed(session)
        errors = []

        def toggle(n):
            s = SessionFactory()
            try:
                word_service.toggle_favorite(s, 1, ext={"name": "競合"})
            except Exception as e:
                errors.append((n, str(e)))
            finally:
                s.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            for f in as_completed([pool.submit(toggle, i) for i in range(10)]):
                f.result()
        assert len(errors) == 0, f"并发 toggle 失败: {errors}"
        # 最终状态由最后一次 toggle 决定，只需确认没崩溃

    @pytest.mark.xfail(reason="SQLite 单写者限制，并发写入需 MySQL/PostgreSQL")
    def test_parallel_save_same_word(self, session):
        """多个线程保存同一个词，不应重复."""
        errors = []

        def save(n):
            s = SessionFactory()
            try:
                word_service._save_words_as_mastered(s, [{
                    "name": "並列", "kana": "へいれつ", "translation": "并行",
                }])
            except Exception as e:
                errors.append((n, str(e)))
            finally:
                s.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            for f in as_completed([pool.submit(save, i) for i in range(5)]):
                f.result()
        assert len(errors) == 0
        cnt = session.query(Word).filter(Word.name == "並列").count()
        assert cnt == 1

    def test_50_concurrent_reads(self, session):
        """50 个并发读取应全部成功."""
        for i in range(50):
            w = Word(name=f"r{i}", kana="りーど", translation=f"read{i}")
            session.add(w)
            session.flush()
            session.add(Favorite(word_id=w.id, user_id="default", status="mastered"))
        session.commit()

        errors = []

        def read_page():
            s = SessionFactory()
            try:
                word_service.get_mastered_words(s, page=1, page_size=10)
            except Exception as e:
                errors.append(str(e))
            finally:
                s.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            for f in as_completed([pool.submit(read_page) for _ in range(50)]):
                f.result()
        assert len(errors) == 0

    def test_concurrent_mark_learned(self, session):
        """并发标记学习不应重复或崩溃."""
        self._seed(session)
        word_service.toggle_favorite(session, 1, ext={"name": "競合"})
        wid = session.query(Word).filter(Word.name == "競合").first().id
        errors = []

        def mark(n):
            s = SessionFactory()
            try:
                word_service.mark_as_learned(s, wid)
            except Exception as e:
                errors.append((n, str(e)))
            finally:
                s.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            for f in as_completed([pool.submit(mark, i) for i in range(5)]):
                f.result()
        assert len(errors) == 0


class TestConcurrentUserScenarios:
    """模拟真实用户场景."""

    @pytest.mark.xfail(reason="SQLite 单写者限制，并发写入需 MySQL/PostgreSQL")
    def test_mixed_read_write(self, session):
        """混合读写：一些线程读列表，一些线程切换状态."""
        names = [f"u{i}" for i in range(10)]
        for n in names:
            w = Word(name=n, kana="ゆーざー", translation="用户")
            session.add(w)
            session.flush()
            session.add(Favorite(word_id=w.id, user_id="default", status="mastered"))
        session.commit()

        errors = []

        def read():
            s = SessionFactory()
            try:
                word_service.get_mastered_words(s, page=1, page_size=5)
            except Exception as e:
                errors.append(("read", str(e)))
            finally:
                s.close()

        def toggle(i):
            s = SessionFactory()
            try:
                word_service.toggle_favorite(s, i + 1, ext={"name": names[i]})
            except Exception as e:
                errors.append(("toggle", str(e)))
            finally:
                s.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(read) for _ in range(5)] + [pool.submit(toggle, i) for i in range(5)]
            for f in as_completed(futs):
                f.result()
        assert len(errors) == 0


class TestPerformance:
    """性能基准测试."""

    def test_pagination_speed(self, session):
        """200 条数据下，分页和统计应在合理时间内完成."""
        import time
        for i in range(200):
            w = Word(name=f"sp{i}", kana="すぴーど", translation=f"speed{i}")
            session.add(w)
            session.flush()
            session.add(Favorite(word_id=w.id, user_id="default", status="mastered"))
        session.commit()

        start = time.perf_counter()
        for _ in range(10):
            word_service.get_mastered_words(session, page=1, page_size=30)
        read_ms = (time.perf_counter() - start) / 10 * 1000

        start = time.perf_counter()
        for _ in range(10):
            word_service.get_mastered_type_counts(session)
        count_ms = (time.perf_counter() - start) / 10 * 1000

        # 阈值根据环境调整，主要确保不退化
        assert read_ms < 200, f"分页查询过慢: {read_ms:.1f}ms"
        assert count_ms < 100, f"统计查询过慢: {count_ms:.1f}ms"

    def test_bulk_toggle(self, session):
        """批量切换收藏不应超时."""
        for i in range(200):
            w = Word(name=f"bt{i}", kana="ばるく", translation=f"bulk{i}")
            session.add(w)
            session.flush()
            session.add(Favorite(word_id=w.id, user_id="default", status="mastered"))
        session.commit()

        import time
        start = time.perf_counter()
        for i in range(200):
            word_service.toggle_favorite(session, i + 1, ext={"name": f"bt{i}"})
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed / 200 < 50, f"toggle 平均 {(elapsed/200):.1f}ms"
