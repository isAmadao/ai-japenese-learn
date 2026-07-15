# 开发日志 2026-06-14 — Nginx 代理 + 字典预载 + 句子换新 + 架构分析

## 概述

新增 Nginx 反向代理作为统一入口，将 LLM 实时生成词库替换为 14,307 词预载词典（零成本），新增"句子换新"AI 例句重写功能，并基于 Milvus-Lite 实现通用文本相似度去重。

## 改动明细

### 1. Nginx 反向代理

| 文件 | 说明 |
|------|------|
| `nginx/nginx.conf` | 🆕 完整反向代理配置：前端静态文件托管（强缓存）+ API 反向代理（含 SSE 流式支持）+ Gzip + 安全头 + 预留 SSL 骨架 |
| `nginx/Dockerfile` | 🆕 多阶段构建：frontend-builder → nginx:alpine |
| `docker-compose.yml` | 🔧 新增 nginx 服务（80 端口）、所有服务移入 app_net 内部网络、保留 8000 端口用于后端调试 |
| `backend/app/main.py` | 🔧 移除 `ProxyHeadersMiddleware`（Starlette 版本不兼容），改为注释说明后置 Nginx IP 透传 |

### 2. JLPT 词库预载（零 LLM 成本）

| 文件 | 说明 |
|------|------|
| `backend/scripts/convert_anki_jlpt.py` | 🆕 Anki CSV → 字典 JSON 转换脚本 |
| `backend/data/dictionary/jlpt_words.json` | 🆕 14,307 词 JLPT 词典（firavoyage Anki 牌组，CC-BY-NC-SA 许可） |
| `backend/app/core/dictionary/jlpt_words.json` | 🆕 Docker 构建用副本 |
| `backend/app/core/database.py` | 🔧 新增 `_load_dict()` 启动时自动加载词典到 Word 表 |
| `backend/app/services/word_service.py` | 🔧 大改：移除整个词池机制 + LLM 生成，改为 `_pick_random_dict_words()` 从字典随机取未学过的词 |
| `backend/app/agent/word_agent.py` | 🔧 移除 `generate_words_stream()`（不再需要 LLM 实时生成） |
| `.dockerignore` | 🔧 从 `backend/data` 改为只排除 `*.db`，保留词典文件 |

词库分布:
- N5: 829, N4: 789, N3: 1,673, N2: 3,213, N1: 7,803

### 3. "句子换新"功能

| 文件 | 说明 |
|------|------|
| `backend/app/agent/word_agent.py` | 🔧 新增 `enrich_sentences()` — 调用 LLM 为单个词生成 3 个新例句 |
| `backend/app/api/words.py` | 🔧 新增 `POST /api/words/{id}/refresh-sentences` 端点 |
| `backend/app/services/word_service.py` | 🔧 新增 `refresh_word_sentences()` — 追加新句子到现有例句 |
| `frontend/src/api/index.ts` | 🔧 新增 `refreshWordSentences()` API 函数 |
| `frontend/src/views/WordDetail.vue` | 🔧 新增 "✨ 句子换新" 按钮（仅非缓存词显示） |

### 4. 通用文本相似度去重（Milvus-Lite）

| 文件 | 说明 |
|------|------|
| `backend/app/core/milvus_client.py` | 🔧 新增 `sentence_vectors` 集合（1024-d 向量） |
| `backend/app/agent/base_agent.py` | 🔧 新增 `dedup_by_text()` 通用方法 — DashScope Embedding → Milvus 搜索 → 阈值过滤 |
| `backend/app/services/word_service.py` | 🔧 句子换新时调用 dedup，相似度 ≥ 0.99 的不再追加 |

`dedup_by_text()` 通过换 `collection` 参数可复用于：
- `word_vectors` — 单词语义去重
- `article_vectors` — 文章相似度检测
- `sentence_vectors` — 例句去重（当前使用）

### 5. JSON 解析容错

| 文件 | 说明 |
|------|------|
| `backend/app/agent/base_agent.py` | 🔧 `_extract_json()` 修复失败后自动修复常见 LLM JSON 错误：补缺失逗号、去尾随逗号 |

## 词典来源

- **数据**: [firavoyage/_anki-jlpt-decks](https://github.com/firavoyage/_anki-jlpt-decks)（14,307 词，含中文释义 + 例句）
- **转换脚本**: `backend/scripts/convert_anki_jlpt.py`
- **运行**: `cd backend && python scripts/convert_anki_jlpt.py`

## 后续方向（与成熟 App 对比分析）

| 优先级 | 方向 | 说明 |
|--------|------|------|
| 🔴 SRS 复习系统 | Anki、Renshuu | 根据掌握程度自动安排复习间隔（1d→3d→7d→1m），核心功能 |
| 🔴 测验/练习 | Renshuu、Bunpo | 看中文选日语、听力选择、拼写填空、阅读理解 |
| 🔴 阅读增强 | Migaku、Satori | 文章中点击单词即时释义、一键收藏、难度标注 |
| 🔴 学习统计 | Duolingo、Renshuu | 每日学习量、复习趋势、薄弱词分析 |
| 🟡 文法学习 | Bunpo、Tae Kim | JLPT 文法条目（～てしまう等），含说明和例句 |
| 🟡 汉字详情 | WaniKani、Kanji Study | 音读/训读、笔画顺序、构成部件 |
| 🟡 自定义词单 | 几乎所有 | 按主题分类（旅行/商务/日常） |
| 🔵 浏览器插件 | Migaku / Yomitan | 阅读日文网页时自动取词 |
| 🔵 发音评测 | - | 录音 + AI 分析 |

## 验证

- `http://localhost` → Nginx 前端页面 ✅
- `http://localhost:8000` → 后端直连 ✅
- `http://localhost:8000/docs` → Swagger ✅
- 词库 14,307 词加载 ✅
- "换一批" 零成本瞬间展示 ✅
- "句子换新" 追加 3 句 + 去重 ✅
- Docker 构建和运行 ✅
