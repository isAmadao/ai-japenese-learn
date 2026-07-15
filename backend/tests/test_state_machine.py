"""Critical path test: status machine transitions.

Status flow:
  mastered ──★──→ favorite ──✅──→ learned ──🎯──→ mastered
    ↑_______________★取消收藏_______________|
"""

import pytest
from app.models.word import Word
from app.models.favorite import Favorite
from app.services.word_service import word_service


class TestStateMachine:
    """Test all status transitions and edge cases."""

    # ── helpers ──────────────────────────────────────────────

    def _create_word(self, db, name: str = "テスト") -> int:
        """Helper: insert a Word + Favorite(mastered), return word_id."""
        w = Word(name=name, kana="テスト", translation="测试")
        db.add(w)
        db.flush()
        db.add(Favorite(word_id=w.id, user_id="default", status="mastered"))
        db.commit()
        return w.id

    def _get_status(self, db, word_id: int) -> str:
        fav = db.query(Favorite).filter(Favorite.word_id == word_id).first()
        return fav.status if fav else None

    # ── Happy path ───────────────────────────────────────────

    def test_full_cycle(self, db):
        """mastered → favorite → learned → mastered"""
        wid = self._create_word(db, "自転車")

        # mastered → favorite
        r = word_service.toggle_favorite(db, 1, ext={"name": "自転車"})
        assert r["is_favorited"] is True
        assert self._get_status(db, wid) == "favorite"

        # favorite → learned
        r = word_service.mark_as_learned(db, wid)
        assert r["success"] is True
        assert self._get_status(db, wid) == "learned"

        # learned → mastered
        r = word_service.mark_as_mastered(db, wid)
        assert r["success"] is True
        assert self._get_status(db, wid) == "mastered"

    # ── Toggle (双向) ────────────────────────────────────────

    def test_toggle_mastered_to_favorite_and_back(self, db):
        """mastered → favorite → mastered"""
        wid = self._create_word(db, "本")

        # mastered → favorite
        r = word_service.toggle_favorite(db, 1, ext={"name": "本"})
        assert r["is_favorited"] is True
        assert self._get_status(db, wid) == "favorite"

        # favorite → mastered (取消收藏)
        r = word_service.toggle_favorite(db, 1, ext={"name": "本"})
        assert r["is_favorited"] is False
        assert self._get_status(db, wid) == "mastered"

    def test_toggle_from_none(self, db):
        """No record → favorite (首次收藏新词)"""
        w = Word(name="猫", kana="ねこ", translation="猫")
        db.add(w)
        db.commit()
        wid = w.id

        r = word_service.toggle_favorite(db, 99, ext={"name": "猫"})
        assert r["is_favorited"] is True
        assert self._get_status(db, wid) == "favorite"

    # ── Edge cases ───────────────────────────────────────────

    def test_mark_learned_only_from_favorite(self, db):
        """mastered 状态的词不能直接标记为 learned"""
        wid = self._create_word(db, "車")
        r = word_service.mark_as_learned(db, wid)
        assert r["success"] is False
        assert "未收藏" in r["message"]

    def test_mark_mastered_only_from_learned(self, db):
        """favorite 状态的词不能直接标记为 mastered"""
        wid = self._create_word(db, "飛行機")
        word_service.toggle_favorite(db, 1, ext={"name": "飛行機"})
        # 已经是 favorite，尝试标记 mastered
        r = word_service.mark_as_mastered(db, wid)
        assert r["success"] is False

    def test_toggle_missing_ext(self, db):
        """不传 ext 应返回错误"""
        r = word_service.toggle_favorite(db, 1, ext=None)
        assert r["is_favorited"] is False
        assert "缺少单词数据" in r["message"]

    def test_toggle_empty_name_in_ext(self, db):
        """ext 中 name 为空也应返回错误"""
        r = word_service.toggle_favorite(db, 1, ext={"name": ""})
        assert r["is_favorited"] is False

    def test_mark_learned_nonexistent_word(self, db):
        """不存在的 word_id 标记 learned 应失败"""
        r = word_service.mark_as_learned(db, 99999)
        assert r["success"] is False

    def test_mark_mastered_nonexistent_word(self, db):
        """不存在的 word_id 标记 mastered 应失败"""
        r = word_service.mark_as_mastered(db, 99999)
        assert r["success"] is False

    # ── Pagination edge cases ────────────────────────────────

    def test_get_mastered_words_empty(self, db):
        """没有 mastered 词时应返回空列表"""
        result = word_service.get_mastered_words(db)
        assert result["words"] == []
        assert result["total"] == 0

    def test_get_mastered_words_pagination(self, db):
        """大量 mastered 词时分页正确"""
        for i in range(5):
            w = Word(name=f"単語{i}", kana=f"たんご{i}", translation=f"单词{i}")
            db.add(w)
            db.flush()
            db.add(Favorite(word_id=w.id, user_id="default", status="mastered"))
        db.commit()

        # page 1, page_size=2
        r1 = word_service.get_mastered_words(db, page=1, page_size=2)
        assert len(r1["words"]) == 2
        assert r1["total"] == 5
        assert r1["total_pages"] == 3

        # page 3 (last)
        r3 = word_service.get_mastered_words(db, page=3, page_size=2)
        assert len(r3["words"]) == 1

    def test_save_word_as_mastered_idempotent(self, db, sample_word_data):
        """多次保存同一个词不应创建重复记录（模拟真实批处理流程）"""
        word_service._save_words_as_mastered(db, [sample_word_data])
        word_service._save_words_as_mastered(db, [sample_word_data])
        word_service._save_words_as_mastered(db, [sample_word_data])

        count = db.query(Word).filter(Word.name == "食べる").count()
        assert count == 1  # 只应有一条

        fav_count = (
            db.query(Favorite)
            .join(Word)
            .filter(Word.name == "食べる")
            .count()
        )
        assert fav_count == 1  # 只应有一条

    # ── 并发安全性检查 ───────────────────────────────────────

    def test_two_words_same_name(self, db):
        """相同 name 不应创建两个 Word 记录（模拟真实批处理流程）"""
        word_service._save_words_as_mastered(db, [{"name": "同じ", "kana": "おなじ", "translation": "相同"}])
        word_service._save_words_as_mastered(db, [{"name": "同じ", "kana": "おなじ", "translation": "相同"}])
        assert db.query(Word).filter(Word.name == "同じ").count() == 1

    def test_get_word_detail_status(self, db):
        """get_word_detail 应反映正确的 is_favorited"""
        wid = self._create_word(db, "天気")
        detail = word_service.get_word_detail(db, wid)
        assert detail is not None
        assert detail["is_favorited"] is False  # mastered 不是 favorited

        # 收藏后 is_favorited 应为 True
        word_service.toggle_favorite(db, 1, ext={"name": "天気"})
        detail = word_service.get_word_detail(db, wid)
        assert detail["is_favorited"] is True

        # 取消后应为 False
        word_service.toggle_favorite(db, 1, ext={"name": "天気"})
        detail = word_service.get_word_detail(db, wid)
        assert detail["is_favorited"] is False  # 变回 mastered

    def test_get_nonexistent_word_detail(self, db):
        """不存在的 word_id 应返回 None"""
        assert word_service.get_word_detail(db, 99999) is None
