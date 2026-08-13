# AI 补词功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搜索无结果时，用户手动触发 AI 判断 query 是否为日语单词，若是则补充词条入库 + ES 索引，使该词之后可被搜索到。

**Architecture:** 新增 `POST /api/words/ai-add` 端点。`WordAgent.analyze_word` 单次 LLM 调用完成"判定 + 生成"；`word_service.add_missing_word` 负责门控、限频、缓存、DB 查重/入库、ES 单文档增量索引（全部同步）；前端 `Search.vue` 在无结果状态下显示按钮并处理结果。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite、Elasticsearch（BM25）、Redis（限频/缓存）、Qwen LLM（langchain-openai）、Vue 3 + Vite。测试：pytest（后端，无前端单测）。

## Global Constraints

- **Git 提交策略**：不自动 `git add` / `git commit`。每个任务最后一步是「人工核验」，由开发者验证通过后再决定提交方式（见 CLAUDE.md 第 4 条）。
- **功能边界控制**：只改目标功能涉及的文件，不波及无关模块。
- **后端测试**：`cd backend && python -m pytest tests/test_ai_add.py -v`（conda 环境 `ai-japenese-learn`，注意拼写）。conftest 已 mock LLM / Redis / Milvus。
- **前端测试**：无单测，本地 `npm run dev` + 后端手动验证，账号 `admin/admin`。
- **ES**：`localhost:9200`，索引 `jp_words`，`refresh_interval` 为 30s —— 补词后必须 `es.indices.refresh()` 强制刷新，否则新词最多 30s 后才会被搜到。
- **ES 单文档 embedding 维度**：以 `jp_words` 索引 mapping 里的 `embedding.dims` 为准；用 `vector_service.embed_local()` 生成的向量若维度匹配则带上，不匹配则省略（BM25 仍可搜）。
- **api_key 约定**：请求体可选传用户自己的 key，默认用 `settings.LLM_API_KEY`（沿用 refresh-sentences 模式）。

---

### Task 1: `looks_japanese` 工具函数 + `WordAgent.analyze_word`

**Files:**
- Modify: `backend/app/services/japanese_util.py`（追加 `looks_japanese`）
- Modify: `backend/app/agent/word_agent.py`（追加 `analyze_word` 方法）
- Create: `backend/tests/test_ai_add.py`

**Interfaces:**
- Produces: `looks_japanese(text: str) -> bool`；`WordAgent.analyze_word(query: str, api_key: Optional[str] = None) -> dict`（返回 `{"is_japanese": False, "reason": "..."}` 或 `{"is_japanese": True, "word": {name, kana, translation, description, type, example_sentences}}`）

- [ ] **Step 1: 在 `japanese_util.py` 末尾追加 `looks_japanese`**

```python
def looks_japanese(text: str) -> bool:
    """粗略判断字符串是否含日语字符（平假名/片假名/CJK 汉字）。

    用于 AI 补词的前端/后端门控。注意 CJK 区含中文汉字，无法区分中文，
    所以这只是过滤 ASCII/数字/乱码的粗筛，最终判断交给 LLM。
    """
    for ch in text:
        cp = ord(ch)
        if 0x3040 <= cp <= 0x309F:   # 平假名
            return True
        if 0x30A0 <= cp <= 0x30FF:   # 片假名
            return True
        if 0x4E00 <= cp <= 0x9FFF:   # CJK 统一表意文字
            return True
    return False
```

- [ ] **Step 2: 在 `word_agent.py` 的 `WordAgent` 类中追加 `analyze_word` 方法（放在 `enrich_sentences` 之后、`store_vector` 之前）**

```python
def analyze_word(self, query: str, api_key: Optional[str] = None) -> dict:
    """判断 query 是否为日语单词；若是则生成完整词条。

    *api_key* overrides the instance/default API key for this call.
    Returns one of:
      {"is_japanese": False, "reason": "..."}
      {"is_japanese": True, "word": {name, kana, translation, description, type, example_sentences}}
    """
    system_msg = "你是一位专业的日语教师。请判断输入的词是否是一个日语单词，并始终用JSON格式回复。"
    user_prompt = f"""请判断「{query}」是否是一个日语单词。

如果它是一个日语单词（汉字/假名/片假名，包括外来语），返回：
{{"is_japanese": true, "word": {{
  "name": "日语表记（若 query 是假名，则给出常见的汉字写法；若无汉字则用假名）",
  "kana": "平假名读音",
  "translation": "中文释义",
  "description": "简要用法说明或记忆提示（一两句话）",
  "type": "N1-N5 难度级别",
  "example_sentences": [{{"japanese": "日语句子", "chinese": "中文翻译"}}, ...3个]
}}}}

如果不是日语单词（是中文、英文、乱码等），返回：
{{"is_japanese": false, "reason": "简要说明它为什么不是日语单词"}}

只返回JSON，不要其他内容。"""
    raw = self._generate(system_msg, user_prompt, use_cache=False, api_key=api_key)
    try:
        data = extract_json(raw)
    except Exception as e:
        logger.warning(f"analyze_word parse failed: {e}")
        raise RuntimeError(f"AI 解析失败: {e}")

    if not isinstance(data, dict):
        raise RuntimeError("AI 返回格式异常")

    if not data.get("is_japanese"):
        return {"is_japanese": False, "reason": data.get("reason", "该词看起来不是日语单词")}

    word = data.get("word")
    if not isinstance(word, dict) or not word.get("name"):
        raise RuntimeError("AI 未返回有效的单词信息")

    name = word["name"]
    kana = word.get("kana", "")
    if kana:
        corrected = verify_kana(name, kana)
        if corrected:
            word["kana"] = corrected
    if not word.get("type"):
        word["type"] = "N1"
    if not word.get("translation"):
        word["translation"] = ""
    sentences = word.get("example_sentences", []) or []
    word["example_sentences"] = [
        s for s in sentences
        if isinstance(s, dict) and s.get("japanese") and s.get("chinese")
    ][:3]
    return {"is_japanese": True, "word": word}
```

- [ ] **Step 3: 创建 `backend/tests/test_ai_add.py`（Task 1 的测试先写 `looks_japanese` 和 `analyze_word` 部分）**

```python
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

        monkeypatch.setattr(wa.word_agent, "_generate", fake_generate)

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

        monkeypatch.setattr(wa.word_agent, "_generate", fake_generate)
        result = wa.word_agent.analyze_word("电脑")
        assert result["is_japanese"] is False
        assert "中文" in result["reason"]

    def test_parse_error_raises(self, monkeypatch):
        from app.agent import word_agent as wa

        def fake_generate(self, system_msg, user_prompt, **kw):
            return "不是JSON内容"

        monkeypatch.setattr(wa.word_agent, "_generate", fake_generate)
        with pytest.raises(RuntimeError):
            wa.word_agent.analyze_word("謄本")

    def test_missing_word_field_raises(self, monkeypatch):
        from app.agent import word_agent as wa

        def fake_generate(self, system_msg, user_prompt, **kw):
            return json.dumps({"is_japanese": True, "word": {"kana": "とうほん"}})

        monkeypatch.setattr(wa.word_agent, "_generate", fake_generate)
        with pytest.raises(RuntimeError):
            wa.word_agent.analyze_word("謄本")
```

- [ ] **Step 4: 运行测试，确认失败（新方法尚未实现）**

Run: `cd backend && python -m pytest tests/test_ai_add.py -v`
Expected: FAIL（`analyze_word` / `looks_japanese` 不存在）

- [ ] **Step 5: 实现后重跑，确认通过**

Run: `cd backend && python -m pytest tests/test_ai_add.py -v`
Expected: PASS（全部绿）

- [ ] **Step 6: 人工核验（不提交 git）**
检查：`looks_japanese` 对假名/片假名/汉字返回 True；对 ascii/数字返回 False；`analyze_word` 能正确解析两种 JSON 形态。

---

### Task 2: `word_service.add_missing_word` + ES 增量索引

**Files:**
- Modify: `backend/app/services/word_service.py`
- Modify: `backend/tests/test_ai_add.py`（追加测试）

**Interfaces:**
- Consumes: `looks_japanese`（Task 1）、`word_agent.analyze_word`（Task 1）、`Word.to_dict()`
- Produces: `WordService.add_missing_word(db: Session, query: str, user_id: str, api_key: Optional[str] = None) -> dict`，返回 status ∈ `"added" | "found" | "not_japanese" | "rate_limited" | "invalid"`。`WordService._index_word_to_es(word: Word) -> None`

- [ ] **Step 1: 在 `word_service.py` 顶部加 `import hashlib`**

```python
import hashlib
```

- [ ] **Step 2: 在 `word_service.py` 的模块级常量区（`_SESSION_CACHE_PREFIX` 附近）追加 AI 补词常量**

```python
# ── AI 补词（search miss → LLM enrich）────────────────────
AI_ADD_RATE_LIMIT_SECONDS = 30
AI_ADD_CACHE_TTL_SUCCESS = 7 * 24 * 3600   # 7 days — 成功词条
AI_ADD_CACHE_TTL_REJECT = 24 * 3600        # 24h — 非日语拒绝结论
```

- [ ] **Step 3: 在 `WordService` 类中追加两个方法（放在 `search_words` 方法之后）**

```python
    # ═══════════════════════════════════════════════════════
    #  AI 补词 — search miss → LLM 判定并生成 → 入库 + ES 增量
    # ═══════════════════════════════════════════════════════

    def add_missing_word(
        self, db: Session, query: str, user_id: str,
        api_key: Optional[str] = None,
    ) -> dict:
        """AI 补词主流程（全部同步）。

        返回 status ∈ {"added", "found", "not_japanese", "rate_limited", "invalid"}。
        """
        q = query.strip() if query else ""
        if not q:
            return {"status": "invalid", "reason": "查询为空"}

        # ── 门控：明显非日语（无假名/片假名/汉字）──
        from app.services.japanese_util import looks_japanese
        if not looks_japanese(q):
            return {"status": "invalid", "reason": "输入内容看起来不是日语单词"}

        # ── 限频 ──
        rate_key = f"rate:ai_add:{user_id}"
        if redis_client._sync_get(rate_key):
            return {"status": "rate_limited"}
        redis_client._sync_set(rate_key, "1", ttl=AI_ADD_RATE_LIMIT_SECONDS)

        # ── 结果缓存 ──
        cache_key = f"ai_add:{hashlib.sha256(q.encode('utf-8')).hexdigest()[:16]}"
        cached = redis_client._sync_get(cache_key)
        if cached:
            return json.loads(cached)

        # ── DB 查重（词库里已有，但 ES 索引可能缺失/陈旧 → 顺手补进 ES）──
        existing = db.query(Word).filter(
            (Word.name == q) | (Word.kana == q)
        ).first()
        if existing:
            try:
                self._index_word_to_es(existing)
            except Exception as e:
                logger.warning(f"ES index failed for existing word {existing.name}: {e}")
            result = {"status": "found", "word": existing.to_dict(), "new": False}
            redis_client._sync_set(cache_key, json.dumps(result, ensure_ascii=False), ttl=AI_ADD_CACHE_TTL_SUCCESS)
            return result

        # ── LLM 判定 + 生成 ──
        analysis = word_agent.analyze_word(q, api_key=api_key)
        if not analysis["is_japanese"]:
            result = {
                "status": "not_japanese",
                "reason": analysis.get("reason", "该词看起来不是日语单词"),
                "new": False,
            }
            redis_client._sync_set(cache_key, json.dumps(result, ensure_ascii=False), ttl=AI_ADD_CACHE_TTL_REJECT)
            return result

        w = analysis["word"]

        # ── 再查重（LLM 可能规范化了 name）──
        dup = db.query(Word).filter(
            (Word.name == w["name"]) | (Word.kana == w.get("kana", ""))
        ).first()
        if dup:
            result = {"status": "found", "word": dup.to_dict(), "new": False}
            redis_client._sync_set(cache_key, json.dumps(result, ensure_ascii=False), ttl=AI_ADD_CACHE_TTL_SUCCESS)
            return result

        # ── 入库 ──
        word = Word(
            name=w["name"],
            kana=w.get("kana", ""),
            translation=w.get("translation", ""),
            description=w.get("description"),
            type=w.get("type"),
            example_sentences=w.get("example_sentences", []),
        )
        db.add(word)
        db.commit()
        db.refresh(word)

        # ── ES 增量索引（尽力而为，失败不影响已入库）──
        try:
            self._index_word_to_es(word)
        except Exception as e:
            logger.warning(f"ES index failed for {word.name}: {e}")

        result = {"status": "added", "word": word.to_dict(), "new": True}
        redis_client._sync_set(cache_key, json.dumps(result, ensure_ascii=False), ttl=AI_ADD_CACHE_TTL_SUCCESS)
        return result

    def _index_word_to_es(self, word: Word) -> None:
        """单文档写入 jp_words 索引 + 强制刷新（尽力而为）。"""
        from elasticsearch import Elasticsearch
        es = Elasticsearch(["http://localhost:9200"], request_timeout=10)

        # 读取 embedding 维度（按索引 mapping 为准）
        if not hasattr(self, "_es_embedding_dim"):
            mapping = es.indices.get_mapping(index="jp_words")
            self._es_embedding_dim = (
                mapping["jp_words"]["mappings"]["properties"]
                .get("embedding", {})
                .get("dims", 0)
            )

        doc = {
            "name": word.name,
            "kana": word.kana,
            "translation": word.translation,
            "type": word.type or "",
            "description": word.description or "",
        }
        # 向量：维度匹配才带，否则省略（BM25 仍可搜）
        from app.services.vector_service import vector_service
        vec = vector_service.embed_local(f"{word.name} {word.kana} {word.translation}")
        if vec and self._es_embedding_dim and len(vec) == self._es_embedding_dim:
            doc["embedding"] = vec

        es.index(index="jp_words", id=word.id, document=doc)
        # refresh_interval=30s → 必须强制刷新，补完即可搜
        es.indices.refresh(index="jp_words")
```

- [ ] **Step 4: 追加 `add_missing_word` 的测试到 `test_ai_add.py`**

```python
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
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_ai_add.py -v`
Expected: PASS（如 conftest 的 autouse mock 与某测试冲突，按报错微调该测试的 mock 顺序）

- [ ] **Step 6: 人工核验（不提交 git）**
检查：`add_missing_word` 五种 status 分支齐全；ES 写失败不影响入库；限频/缓存 key 命名一致。

---

### Task 3: Schemas + 端点 `POST /api/words/ai-add`

**Files:**
- Modify: `backend/app/schemas/word.py`
- Modify: `backend/app/api/words.py`
- Modify: `backend/tests/test_ai_add.py`（追加测试）

**Interfaces:**
- Consumes: `word_service.add_missing_word`（Task 2）
- Produces: `AiAddRequest`（query, api_key）、`AiAddResponse`（status, word?, new?, reason?）；端点 `POST /api/words/ai-add`

- [ ] **Step 1: 在 `schemas/word.py` 末尾追加 schema**

```python
class AiAddRequest(BaseModel):
    query: str
    api_key: Optional[str] = None


class AiAddResponse(BaseModel):
    status: str
    word: Optional[dict] = None
    new: bool = False
    reason: Optional[str] = None
```

- [ ] **Step 2: 在 `words.py` 中，把 `AiAddRequest, AiAddResponse` 加入现有的 schema 导入**

在现有 `from app.schemas.word import (...)` 的括号内追加两个名字：

```python
    AiAddRequest,
    AiAddResponse,
```

- [ ] **Step 3: 在 `words.py` 的 `search_words` 之后、`/{word_id}` 路由之前插入端点**

```python
@router.post("/ai-add", response_model=AiAddResponse)
def ai_add_word(
    body: AiAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 补词 — 判断 query 是否为日语单词，若是则补充词条入库 + ES 索引。

    必须放在 /{word_id} 路由之前注册，避免路径歧义。
    """
    result = word_service.add_missing_word(
        db, body.query, user_id=str(current_user.id), api_key=body.api_key,
    )
    if result.get("status") == "rate_limited":
        raise HTTPException(status_code=429, detail="操作太频繁，请稍后再试")
    if result.get("status") == "invalid":
        raise HTTPException(status_code=400, detail=result.get("reason", "参数无效"))
    return AiAddResponse(**result)
```

- [ ] **Step 4: 追加端点测试到 `test_ai_add.py`**

```python
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

    def test_invalid_400(self, client, monkeypatch):
        from app.services import word_service as ws

        def fake(db, query, user_id, api_key=None):
            return {"status": "invalid", "reason": "输入内容看起来不是日语单词"}

        monkeypatch.setattr(ws.word_service, "add_missing_word", fake)
        resp = client.post("/api/words/ai-add", json={"query": "hello"})
        assert resp.status_code == 400
        assert "日语" in resp.json()["detail"]
```

- [ ] **Step 5: 运行全部后端测试，确认无回归**

Run: `cd backend && python -m pytest -v`
Expected: 原有测试 + 新增测试全部 PASS

- [ ] **Step 6: 人工核验（不提交 git）**
检查：`POST /api/words/ai-add` 四种响应（200 added / 200 not_japanese / 429 / 400）与设计一致；路由注册在 `/{word_id}` 之前。

---

### Task 4: 前端 — `aiAddWord` + `Search.vue` 按钮与结果处理

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/views/Search.vue`

**Interfaces:**
- Produces: `aiAddWord(query: string, apiKey?: string) -> Promise<AiAddResult>`；`AiAddResult = {status: 'added'|'found'|'not_japanese', word?: SearchResultItem|null, new?: boolean, reason?: string}`

- [ ] **Step 1: 在 `api/index.ts` 的 `searchWordsByImage` 之后追加**

```ts
// ── AI 补词 — 搜索无结果时用 LLM 判断并补充日语单词 ──────

export interface AiAddResult {
  status: 'added' | 'found' | 'not_japanese'
  word?: SearchResultItem | null
  new?: boolean
  reason?: string
}

export async function aiAddWord(query: string, apiKey?: string): Promise<AiAddResult> {
  const body: Record<string, any> = { query }
  if (apiKey) body.api_key = apiKey
  const { data } = await http.post('/words/ai-add', body)
  return data
}
```

- [ ] **Step 2: 在 `Search.vue` 顶部导入 `aiAddWord`（并确保 `SearchResultItem` 类型已导入，通常来自 `@/types`）**

```ts
import { searchWords, searchWordsByImage, aiAddWord } from '@/api'
import type { SearchResultItem } from '@/types'
```

注：若 `SearchResultItem` 已由 `@/types` 导入（`results` 的 ref 类型很可能已用它），则无需重复导入；按现有 import 语句合并。`SearchResultItem` 字段为 `{ id, name, kana, translation, description, type, score }`。

- [ ] **Step 3: 在 `Search.vue` script 的 `doTextSearch` 之后追加 AI 补词逻辑**

```ts
// ── AI 补词 ────────────────────────────────────────────────
const aiAdding = ref(false)
const aiAddMsg = ref('')
const aiAddedId = ref<number | null>(null)

function looksJapanese(text: string): boolean {
  // 平假名/片假名/CJK —— 过滤 ASCII/数字，最终判定交给后端 LLM
  return /[぀-ヿ一-鿿]/.test(text)
}

async function handleAiAdd() {
  const q = query.value.trim()
  if (!q) return
  aiAdding.value = true
  aiAddMsg.value = ''
  try {
    const res = await aiAddWord(q)
    if (res.status === 'added' || res.status === 'found') {
      if (res.word) {
        const item: SearchResultItem = {
          id: res.word.id,
          name: res.word.name,
          kana: res.word.kana,
          translation: res.word.translation,
          description: res.word.description || '',
          type: res.word.type || '',
          score: 1.0,
        }
        results.value = [item]
        total.value = 1
        aiAddedId.value = res.new ? res.word.id : null
        aiAddMsg.value = res.status === 'added'
          ? `已把「${res.word.name}」加入词库 ✨`
          : `「${res.word.name}」已在词库中`
      }
    } else if (res.status === 'not_japanese') {
      aiAddMsg.value = res.reason || `「${q}」看起来不是日语单词，无法添加`
    }
  } catch (e: any) {
    aiAddMsg.value = e?.response?.status === 429
      ? '操作太频繁，请稍后再试'
      : 'AI 补词失败，请稍后再试'
  } finally {
    aiAdding.value = false
  }
}
```

- [ ] **Step 4: 修改 `Search.vue` 模板 — 「无结果」块（文本模式）加入按钮与提示**

把文本模式分支改为：

```html
      <template v-if="mode === 'text'">
        <div>没有找到与「{{ query }}」相关的单词</div>
        <div v-if="looksJapanese(query)" class="ai-add-block">
          <button v-if="!aiAdding" class="ai-add-btn" @click="handleAiAdd">
            没有这个词？让 AI 添加 ✨
          </button>
          <span v-else class="ai-adding">AI 正在判断并补充词条…</span>
        </div>
        <p v-if="aiAddMsg" class="ai-add-msg">{{ aiAddMsg }}</p>
      </template>
```

- [ ] **Step 5: 修改 `Search.vue` 模板 — 结果卡片加「AI 添加」徽标**

在 `<span class="result-name">{{ item.name }}</span>` 之后插入：

```html
              <span class="result-name">{{ item.name }}</span>
              <span v-if="aiAddedId === item.id" class="ai-badge">AI 添加</span>
```

- [ ] **Step 6: 在 `Search.vue` 的 `<style scoped>` 中追加样式**

```css
.ai-add-block {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}
.ai-add-btn {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.45rem;
  padding: 10px 16px;
  border: 3px solid var(--golden);
  background: var(--cream);
  color: var(--warm-brown);
  cursor: pointer;
  box-shadow: 2px 2px 0 var(--golden);
  transition: all 0.05s step-start;
}
.ai-add-btn:hover {
  background: var(--golden-light);
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--golden);
}
.ai-adding {
  font-size: 0.8rem;
  color: var(--text-light);
}
.ai-add-msg {
  margin-top: 10px;
  font-size: 0.8rem;
  color: var(--grass-dark);
  text-align: center;
}
.ai-badge {
  margin-left: 6px;
  font-size: 0.55rem;
  padding: 2px 6px;
  border: 2px solid var(--golden);
  color: var(--warm-brown);
  vertical-align: middle;
}
```

- [ ] **Step 7: 手动验证前端（dev server）**
Run: 前端 `npm run dev` + 后端已启动。在搜索页输入「謄本」→ 无结果 → 出现「没有这个词？让 AI 添加 ✨」→ 点击 → loading → 词条出现带「AI 添加」徽标。

- [ ] **Step 8: 人工核验（不提交 git）**
检查：按钮仅在文本模式 + 含日语字符时出现；added/found/not_japanese/429 四类提示正确；结果卡片可点击进详情。

---

### Task 5: 端到端验证（本地）

**Files:** 无（纯验证）

- [ ] **Step 1: 搜「謄本」→ AI 添加 → 再搜索确认**
Run: 搜索页搜「謄本」→ 点 AI 添加 → 词条出现 → 再次搜索「謄本」应能直接搜到（ES 已强制刷新）。

- [ ] **Step 2: 门控验证**
Run: 搜 "hello" / "123" → 不显示 AI 添加按钮；搜「电脑」（中文）→ 显示按钮，点击后返回「不是日语单词」。

- [ ] **Step 3: 限频验证**
Run: 连续快速点击 AI 添加 → 第二次应提示「操作太频繁」。

- [ ] **Step 4: 重复触发验证**
Run: 对已补过的词再点 AI 添加 → 提示「已在词库中」且不重新调用 LLM。

- [ ] **Step 5: ES 不可用兜底**
Run: 停掉 ES（docker stop 或本地进程）→ 点 AI 添加 → 词仍入库，提示成功；搜索走 SQL 兜底仍可找到。

- [ ] **Step 6: 回归**
Run: 原有功能抽查（换一批、收藏、搜索已有关键词如「食べる」）不受影响。

- [ ] **Step 7: 人工核验（不提交 git）**
核对以上全部场景结果，全部通过后由开发者决定提交方式。
