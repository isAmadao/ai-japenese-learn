# AI 补词功能设计 — 搜索无结果时用 LLM 判断并补充日语单词入库

- **日期**: 2026-08-13
- **状态**: ✅ 已确认（待实现）
- **背景**: 搜索「謄本」等生僻词时词库里没有（词典固定为 JLPT 14,307 词），搜不到

## 目标

当用户搜索一个词且词库中没有时，允许用户手动触发 AI 判断：若为日语单词则补充 kana/释义/例句等信息并入 SQLite + ES 索引，使该词之后可被搜索到。

## 已确认的关键决策

1. **手动按钮触发**（不是自动触发）—— 搜不到时显示按钮，用户点击才调用 LLM
2. **前端预判门控** —— 输入不含日语字符（假名/汉字）时不显示按钮，不调用 LLM
3. **简单限频 + 缓存** —— Redis 每用户 30s 冷却；同一 query 结果缓存（含"非日语"拒绝结论）
4. **入库全部同步** —— LLM 返回后 DB insert + ES 单文档索引 + 强制刷新都在响应返回前完成

## 后端设计

### 新端点 `POST /api/words/ai-add`

- 位置: `backend/app/api/words.py`
- 鉴权: `get_current_user`（与搜索一致）
- 请求体: `{ query: string, api_key?: string }`（`api_key` 沿用 refresh-sentences 模式，可选，默认服务器配置）
- 响应:
  - `200 { status: "added", word: {...}, new: true }` — 新词已补全入库
  - `200 { status: "found", word: {...}, new: false }` — 词库里本来就有（如 ES 索引陈旧），返回已有词
  - `200 { status: "not_japanese", reason: "..." }` — LLM 判定非日语
  - `429` — 限频中
  - `400` — query 为空 / 明显非日语被服务端门控拦下

处理流程（`word_service.add_missing_word`）:

```
限频检查(Redis) → 服务端门控(非空 + 含日语字符) → 结果缓存查重
  → LLM 判定生成(WordAgent.analyze_word) → DB 查重 → 入库(Word表)
  → ES 单文档索引 + 强制刷新 → 写结果缓存 → 返回
```

### LLM 判定 + 生成（`WordAgent.analyze_word(query)`）

- **单次 LLM 调用**同时完成"判定是否日语"和"生成完整词条"（最小延迟）
- 返回结构化 JSON（用 `extract_json` 容错解析），二选一形态：

```json
{"is_japanese": false, "reason": "「电脑」是中文，不是日语单词"}
```
```json
{"is_japanese": true, "word": {
  "name":"謄本", "kana":"とうほん", "translation":"副本，抄本",
  "description":"...", "type":"N1", "example_sentences":[{"japanese":"...","chinese":"..."}]
}}
```

- 生成后校验:
  - `verify_kana(name, kana)` 用 MeCab/pykakasi 修正读音
  - LLM 未给 `type` 时默认 `N1`
  - 例句解析异常时留空数组而不是报错

### 入库 + ES 增量索引（`word_service`）

1. **DB 查重**: `Word.name == query` 或 `Word.kana == query` → 存在则返回 `found`（并把该词补进 ES 索引若缺失）
2. **不存在** → 插入 `Word` 表（SQLite）
3. **ES 增量**: 读 `jp_words` 索引 embedding 维度 → `vector_service.embed_local()`
   - 维度匹配 → 带 embedding 写入单文档（`es.index`）
   - 维度不匹配 → 不带 embedding（BM25 可搜即可）
   - **写入后必须 `es.indices.refresh(index="jp_words")` 强制刷新**（import 脚本把 refresh_interval 设为 30s，不刷新则新词最多要等 30s 才可搜）
   - ES 写失败 → 不阻塞响应，DB 已入库，搜索走 SQL 兜底仍能找到
4. **不重跑** `import_words_to_es.py`（全量重嵌不可接受）

### 限频 + 缓存（Redis，`redis_client._sync_*`）

| 项 | key | 规则 |
|---|---|---|
| 限频 | `rate:ai_add:{user_id}` | `setex` 30s；存在 → 429 |
| 结果缓存 | `ai_add:{sha256(query)}` | 命中直接返回；成功词条 TTL 7 天，`not_japanese` TTL 24h |

Redis 不可用时自动降级到内存 `_LocalCache`（现有机制），不报错。

## 前端设计

### `frontend/src/api/index.ts`

```ts
export interface AiAddResult {
  status: 'added' | 'found' | 'not_japanese'
  word?: SearchResultItem
  new?: boolean
  reason?: string
}
export async function aiAddWord(query: string, apiKey?: string): Promise<AiAddResult>
```

### `frontend/src/views/Search.vue`（仅文本搜索模式的"无结果"状态）

1. **门控**: `query` 含日语字符（正则 `[぀-ヿ一-鿿]`）才显示按钮「没有这个词？让 AI 添加 ✨」
2. 点击 → loading 文案「AI 正在判断并补充词条…」
3. 结果处理:
   - `added` → 将 word 插入搜索结果列表（映射为 `SearchResultItem`），卡片带「AI 添加」徽标
   - `found` → 同上但无徽标
   - `not_japanese` → 提示「「query」看起来不是日语单词，无法添加」
   - `429` → 「操作太频繁，请稍后再试」
   - 其他错误 → 通用失败提示
4. 防竞态: 请求期间用户改了 query → 丢弃过期响应

## 测试计划（本地，admin/admin）

| 场景 | 预期 |
|---|---|
| 搜「謄本」→ 点 AI 添加 | 词出现带 AI 标记 → 再搜「謄本」能直接搜到 |
| 搜 "hello" / 「电脑」 | 不显示按钮（门控） |
| curl 绕过门控发中文 | 后端 400 |
| 连续快速点击 | 429 |
| 重复点同一词 | 命中缓存/DB 查重 → `found`，不再调 LLM |
| 停掉 ES 再点 | 入库成功，SQL 兜底可搜 |

## 明确不做（YAGNI）

- 自动触发 / 后台异步补词（已评估，收益小、引入竞态）
- 动词活用形还原（如「食べて」→「食べる」）—— 后续可做，本期不做
- 词库源整体升级到 JMDict —— 单独议题
- AI 补词的审核/举报机制 —— 个人学习应用不需要
- 全量重跑 ES 索引脚本 —— 改单文档增量

## 涉及文件

**后端**
- `backend/app/api/words.py` — 新端点 `POST /api/words/ai-add`
- `backend/app/services/word_service.py` — `add_missing_word` + ES 单文档索引 helper
- `backend/app/agent/word_agent.py` — `analyze_word`
- `backend/app/schemas/word.py` — `AiAddRequest` / `AiAddResponse`

**前端**
- `frontend/src/api/index.ts` — `aiAddWord` + `AiAddResult`
- `frontend/src/views/Search.vue` — 按钮 + 结果处理
