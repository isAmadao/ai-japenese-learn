"""AI 补词功能测试 — looks_japanese / analyze_word / add_missing_word / endpoint。"""

import json

import pytest


class TestLooksJapanese:
    def test_kana(self):
        from app.services.japanese_util import looks_japanese
        assert looks_japanese("とうほん")

    def test_katakana(self):
        from app.services.japanese_util import looks_japanese
        assert looks_japanese("コピー")

    def test_kanji(self):
        from app.services.japanese_util import looks_japanese
        assert looks_japanese("謄本")

    def test_ascii(self):
        from app.services.japanese_util import looks_japanese
        assert not looks_japanese("hello")

    def test_numeric(self):
        from app.services.japanese_util import looks_japanese
        assert not looks_japanese("123")

    def test_empty(self):
        from app.services.japanese_util import looks_japanese
        assert not looks_japanese("")


class TestAnalyzeWord:
    @pytest.fixture
    def mock_llm_analyze(self, monkeypatch):
        """Override conftest 的 autouse mock，返回 analyze_word 需要的 JSON 形态。"""
        from app.agent import word_agent as wa

        def fake_generate(self, system_msg, user_prompt, **kw):
            return json.dumps({
                "is_japanese": True,
                "word": {
                    "name": "謄本",
                    "kana": "とうほん",
                    "translation": "副本，抄本",
                    "description": "公证书的副本",
                    "type": "N1",
                    "example_sentences": [
                        {"japanese": "謄本を取得する", "chinese": "取得副本"},
                        {"japanese": "謄本を確認する", "chinese": "确认副本"},
                        {"japanese": "謄本を提出する", "chinese": "提交副本"},
                    ],
                },
            })

        monkeypatch.setattr(wa.WordAgent, "_generate", fake_generate)

    def test_is_japanese(self, mock_llm_analyze):
        from app.agent.word_agent import word_agent
        result = word_agent.analyze_word("謄本")
        assert result["is_japanese"] is True
        word = result["word"]
        assert word["name"] == "謄本"
        assert word["kana"] == "とうほん"
        assert word["type"] == "N1"
        assert len(word["example_sentences"]) == 3

    def test_not_japanese(self, monkeypatch):
        from app.agent import word_agent as wa

        def fake_generate(self, system_msg, user_prompt, **kw):
            return json.dumps({"is_japanese": False, "reason": "「电脑」是中文"})

        monkeypatch.setattr(wa.WordAgent, "_generate", fake_generate)
        result = wa.word_agent.analyze_word("电脑")
        assert result["is_japanese"] is False
        assert "中文" in result["reason"]

    def test_parse_error_raises(self, monkeypatch):
        from app.agent import word_agent as wa

        def fake_generate(self, system_msg, user_prompt, **kw):
            return "不是JSON内容"

        monkeypatch.setattr(wa.WordAgent, "_generate", fake_generate)
        with pytest.raises(RuntimeError):
            wa.word_agent.analyze_word("謄本")

    def test_missing_word_field_raises(self, monkeypatch):
        from app.agent import word_agent as wa

        def fake_generate(self, system_msg, user_prompt, **kw):
            return json.dumps({"is_japanese": True, "word": {"kana": "とうほん"}})

        monkeypatch.setattr(wa.WordAgent, "_generate", fake_generate)
        with pytest.raises(RuntimeError):
            wa.word_agent.analyze_word("謄本")

    def test_fenced_markdown_response(self, monkeypatch):
        from app.agent import word_agent as wa

        def fake_generate(self, system_msg, user_prompt, **kw):
            return "```json\n" + json.dumps({
                "is_japanese": True,
                "word": {"name": "謄本", "kana": "とうほん", "translation": "副本",
                         "type": "N1",
                         "example_sentences": [{"japanese": "謄本を取得する", "chinese": "取得副本"}]},
            }) + "\n```"

        monkeypatch.setattr(wa.WordAgent, "_generate", fake_generate)
        result = wa.word_agent.analyze_word("謄本")
        assert result["is_japanese"] is True
        assert result["word"]["name"] == "謄本"


class TestAddMissingWord:
    @pytest.fixture
    def mock_analyze(self, monkeypatch):
        """让 analyze_word 返回固定词条。"""
        from app.agent import word_agent as wa

        def fake(query, api_key=None):
            return {
                "is_japanese": True,
                "word": {
                    "name": "謄本",
                    "kana": "とうほん",
                    "translation": "副本，抄本",
                    "description": "公证书的副本",
                    "type": "N1",
                    "example_sentences": [
                        {"japanese": "謄本を取得する", "chinese": "取得副本"},
                    ],
                },
            }

        monkeypatch.setattr(wa.word_agent, "analyze_word", fake)

    @pytest.fixture
    def mock_analyze_not_jp(self, monkeypatch):
        from app.agent import word_agent as wa

        def fake(query, api_key=None):
            return {"is_japanese": False, "reason": "「电脑」是中文"}

        monkeypatch.setattr(wa.word_agent, "analyze_word", fake)

    @pytest.fixture
    def skip_es(self, monkeypatch):
        from app.services import word_service as ws
        monkeypatch.setattr(ws.word_service, "_index_word_to_es", lambda word: None)

    def test_invalid_ascii(self, db, skip_es):
        from app.services.word_service import word_service
        result = word_service.add_missing_word(db, "hello", user_id="u1")
        assert result["status"] == "invalid"

    def test_empty_query(self, db, skip_es):
        from app.services.word_service import word_service
        result = word_service.add_missing_word(db, "  ", user_id="u1")
        assert result["status"] == "invalid"

    def test_added_inserts_word(self, db, skip_es, mock_analyze):
        from app.services.word_service import word_service
        from app.models.word import Word
        result = word_service.add_missing_word(db, "謄本", user_id="u1")
        assert result["status"] == "added"
        assert result["new"] is True
        assert result["word"]["name"] == "謄本"
        row = db.query(Word).filter(Word.name == "謄本").first()
        assert row is not None
        assert row.kana == "とうほん"

    def test_found_existing(self, db, skip_es, mock_analyze):
        from app.services.word_service import word_service
        from app.models.word import Word
        db.add(Word(name="写真", kana="しゃしん", translation="照片"))
        db.commit()
        result = word_service.add_missing_word(db, "写真", user_id="u1")
        assert result["status"] == "found"
        assert result["new"] is False

    def test_not_japanese_via_llm(self, db, skip_es, mock_analyze_not_jp):
        from app.services.word_service import word_service
        result = word_service.add_missing_word(db, "电脑", user_id="u1")
        assert result["status"] == "not_japanese"
        assert "中文" in result["reason"]

    def test_rate_limited(self, db, skip_es, mock_analyze):
        from app.services.word_service import word_service
        word_service.add_missing_word(db, "謄本", user_id="u1")
        result = word_service.add_missing_word(db, "別の語", user_id="u1")
        assert result["status"] == "rate_limited"

    def test_cache_hit_skips_llm(self, db, skip_es, monkeypatch):
        from app.services.word_service import word_service
        from app.agent import word_agent as wa

        def boom(query, api_key=None):
            raise AssertionError("缓存命中不应调用 LLM")

        monkeypatch.setattr(wa.word_agent, "analyze_word", boom)

        # 预置结果缓存（计算与 service 一致的 cache_key）
        import hashlib
        cache_key = f"ai_add:{hashlib.sha256('謄本'.encode('utf-8')).hexdigest()[:16]}"
        from app.core.redis_client import redis_client
        redis_client._sync_set(
            cache_key,
            json.dumps({"status": "added", "word": {"name": "謄本", "kana": "とうほん", "translation": "副本"}, "new": True}, ensure_ascii=False),
            ttl=3600,
        )
        result = word_service.add_missing_word(db, "謄本", user_id="u9")
        assert result["status"] == "added"
        assert result["word"]["name"] == "謄本"

    def test_es_failure_still_adds(self, db, mock_analyze, monkeypatch):
        from app.services import word_service as ws

        def boom(word):
            raise RuntimeError("ES down")

        monkeypatch.setattr(ws.word_service, "_index_word_to_es", boom)
        from app.services.word_service import word_service
        from app.models.word import Word
        result = word_service.add_missing_word(db, "謄本", user_id="u2")
        assert result["status"] == "added"
        assert db.query(Word).filter(Word.name == "謄本").first() is not None


class TestAiAddEndpoint:
    def test_added(self, client, monkeypatch):
        from app.services import word_service as ws

        def fake(db, query, user_id, api_key=None):
            return {"status": "added", "word": {"id": 1, "name": "謄本", "kana": "とうほん", "translation": "副本", "type": "N1"}, "new": True}

        monkeypatch.setattr(ws.word_service, "add_missing_word", fake)
        resp = client.post("/api/words/ai-add", json={"query": "謄本"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "added"
        assert data["word"]["name"] == "謄本"
        assert data["new"] is True

    def test_not_japanese(self, client, monkeypatch):
        from app.services import word_service as ws

        def fake(db, query, user_id, api_key=None):
            return {"status": "not_japanese", "reason": "不是日语"}

        monkeypatch.setattr(ws.word_service, "add_missing_word", fake)
        resp = client.post("/api/words/ai-add", json={"query": "电脑"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_japanese"

    def test_rate_limited_429(self, client, monkeypatch):
        from app.services import word_service as ws

        def fake(db, query, user_id, api_key=None):
            return {"status": "rate_limited"}

        monkeypatch.setattr(ws.word_service, "add_missing_word", fake)
        resp = client.post("/api/words/ai-add", json={"query": "謄本"})
        assert resp.status_code == 429
        assert "太频繁" in resp.json()["detail"]

    def test_api_key_passthrough(self, client, monkeypatch):
        from app.services import word_service as ws
        captured = {}

        def fake(db, query, user_id, api_key=None):
            captured["api_key"] = api_key
            return {"status": "added", "word": {"id": 1, "name": "謄本", "kana": "とうほん", "translation": "副本", "type": "N1"}, "new": True}

        monkeypatch.setattr(ws.word_service, "add_missing_word", fake)
        resp = client.post("/api/words/ai-add", json={"query": "謄本", "api_key": "sk-test"})
        assert resp.status_code == 200
        assert captured["api_key"] == "sk-test"

    def test_invalid_400(self, client, monkeypatch):
        from app.services import word_service as ws

        def fake(db, query, user_id, api_key=None):
            return {"status": "invalid", "reason": "输入内容看起来不是日语单词"}

        monkeypatch.setattr(ws.word_service, "add_missing_word", fake)
        resp = client.post("/api/words/ai-add", json={"query": "hello"})
        assert resp.status_code == 400
        assert "日语" in resp.json()["detail"]


class TestSearchSqlFallbackOnEmpty:
    def test_es_empty_falls_back_to_sql(self, db, monkeypatch):
        import sys
        import types
        from app.services import word_service as ws
        from app.models.word import Word

        class FakeES:
            def __init__(self, *a, **k):
                pass

            def search(self, index=None, size=None, body=None, **k):
                return {"hits": {"hits": []}}

            def close(self):
                pass

        # elasticsearch 真实包在本环境因 opentelemetry 不兼容无法 import。
        # 注入带 Elasticsearch 属性的假模块，让 search_words 内部
        # `from elasticsearch import Elasticsearch` 拿到 FakeES（无需加载真实包）。
        fake_es_module = types.ModuleType("elasticsearch")
        fake_es_module.Elasticsearch = FakeES
        monkeypatch.setitem(sys.modules, "elasticsearch", fake_es_module)

        db.add(Word(name="謄本", kana="とうほん", translation="副本，抄本"))
        db.commit()
        result = ws.word_service.search_words(db, "謄本", top_k=20)
        assert result["total"] == 1
        assert result["results"][0]["name"] == "謄本"
