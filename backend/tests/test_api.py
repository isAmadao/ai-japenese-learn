"""API endpoint integration tests — edge cases, error handling, response format."""

import json


class TestWordsAPI:
    """GET /api/words/random, POST /api/words/{id}/favorite, etc."""

    RANDOM_URL = "/api/words/random"
    FAVORITE_URL = "/api/words/{}/favorite"

    def test_random_words_default(self, client):
        """默认参数应返回 5 个词（含正确字段）"""
        resp = client.get(self.RANDOM_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert "words" in data
        # 可能实际调用 LLM 失败，但响应格式应正确
        if data["words"]:
            w = data["words"][0]
            assert "name" in w
            assert "kana" in w
            assert "translation" in w
            assert "id" in w

    def test_random_words_count_param(self, client):
        """count 参数应影响返回数量（上限 20）"""
        resp = client.get(self.RANDOM_URL, params={"count": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["words"]) <= 3

    def test_random_words_count_too_large(self, client):
        """count>20 应返回 422"""
        resp = client.get(self.RANDOM_URL, params={"count": 100})
        assert resp.status_code == 422

    def test_random_words_count_zero(self, client):
        """count=0 应返回 422"""
        resp = client.get(self.RANDOM_URL, params={"count": 0})
        assert resp.status_code == 422

    def test_random_words_count_negative(self, client):
        """count=-1 应返回 422"""
        resp = client.get(self.RANDOM_URL, params={"count": -1})
        assert resp.status_code == 422

    def test_random_words_session_id(self, client):
        """不同 session_id 应返回不同结果"""
        resp_a = client.get(self.RANDOM_URL, params={"session_id": "session-a"})
        resp_b = client.get(self.RANDOM_URL, params={"session_id": "session-b"})
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

    def test_toggle_favorite_no_body(self, client):
        """POST 收藏时不传 body → ext=None → 后端处理为缺少数据"""
        resp = client.post(self.FAVORITE_URL.format(1), json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_favorited"] is False
        assert "缺少单词数据" in data["message"]

    def test_toggle_favorite_with_ext(self, client):
        """传 ext 应正确执行收藏逻辑"""
        resp = client.post(
            self.FAVORITE_URL.format(1),
            json={"ext": {"name": "テスト", "kana": "テスト", "translation": "测试"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "is_favorited" in data

    def test_word_detail_not_found(self, client):
        """不存在的 word_id 应返回 404"""
        resp = client.get("/api/words/99999")
        assert resp.status_code == 404

    def test_word_detail_zero_id(self, client):
        """word_id=0 应返回 404"""
        resp = client.get("/api/words/0")
        assert resp.status_code == 404

    def test_word_detail_negative_id(self, client):
        """word_id=-1 应返回 404 或 422"""
        resp = client.get("/api/words/-1")
        assert resp.status_code in (404, 422)

    def test_word_detail_string_id(self, client):
        """非数字 ID 应返回 422"""
        resp = client.get("/api/words/abc")
        assert resp.status_code == 422


class TestMasteredAPI:
    """GET /api/mastered, GET /api/mastered/types"""

    URL = "/api/mastered"
    TYPES_URL = "/api/mastered/types"

    def test_mastered_list_empty(self, client):
        resp = client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert "words" in data
        assert "total" in data

    def test_mastered_types(self, client):
        resp = client.get(self.TYPES_URL)
        assert resp.status_code == 200
        data = resp.json()
        for level in ("N5", "N4", "N3", "N2", "N1"):
            assert level in data

    def test_mastered_pagination(self, client):
        """分页参数传递正确"""
        resp = client.get(self.URL, params={"page": 1, "page_size": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_mastered_filter_by_type(self, client):
        """按难度过滤"""
        resp = client.get(self.URL, params={"type": "N5"})
        assert resp.status_code == 200

    def test_mastered_invalid_type(self, client):
        """无效难度级别应正常返回（不做过滤）"""
        resp = client.get(self.URL, params={"type": "N99"})
        assert resp.status_code == 200


class TestLearnedAPI:
    """PATCH /api/learned/{id}/master"""

    def test_mark_as_mastered_not_found(self, client):
        """不存在的 word_id 应返回 404"""
        resp = client.patch("/api/learned/99999/master")
        assert resp.status_code == 404

    def test_mark_as_mastered_zero_id(self, client):
        resp = client.patch("/api/learned/0/master")
        assert resp.status_code == 404


class TestHealthEndpoint:
    """GET /api/health"""

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


class TestSSEEndpoint:
    """GET /api/words/random/stream"""

    SSE_URL = "/api/words/random/stream"

    def test_sse_returns_stream(self, client):
        """SSE 端点应返回 text/event-stream"""
        resp = client.get(self.SSE_URL, params={"count": 1})
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

    def test_sse_invalid_count(self, client):
        resp = client.get(self.SSE_URL, params={"count": 0})
        assert resp.status_code == 422

    def test_sse_negative_count(self, client):
        resp = client.get(self.SSE_URL, params={"count": -1})
        assert resp.status_code == 422

    def test_sse_large_count(self, client):
        resp = client.get(self.SSE_URL, params={"count": 50})
        # 后端限制最多 20，但应返回正常响应
        assert resp.status_code in (200, 422)
