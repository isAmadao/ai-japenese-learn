# 开发日志 2026-06-05 — 核心功能完善 + 容器化 + 架构优化

## 概述

今日对项目进行了大规模改造，涵盖状态机扩展、流式输出、重试机制、容器化部署、词典替换、前端体验优化等多个维度。

## 改动明细

### 1. 首页体验优化

**问题**：项目启动时直接调用 LLM 生成单词，用户无控制权；「换一批」按钮语义不准确。

**方案**：
- 首页首次进入展示「欢迎使用！」欢迎界面，点击「生成新词」才触发 LLM
- 按钮文字动态切换：无词时 →「生成新词」，有词后 →「换一批」
- 去除冗余的「暂无单词数据」空状态提示
- 去除单词详情页误导性的「⚡ 该单词尚未收藏，点击 ★ 收藏后永久保存」（词已永久存于 DB）

### 2. 状态机扩展：新增「已熟练」状态

**问题**：之前的 Favorite 状态只有 `favorite | learned`，LLM 生成的词仅缓存在 Redis，没有持久化。

**方案**：状态机扩展为 `mastered → favorite → learned → mastered`：

```
LLM生成 → mastered(已熟练) → ★收藏 → favorite(收藏) → ✅已学习 → learned(已学习) → 🎯已熟练 → mastered
                    ↑_______________★取消收藏_______________|
```

**改动的文件**：
- `backend/app/services/word_service.py` — 新增 `get_mastered_words()`, `get_mastered_type_counts()`, `mark_as_mastered()`；`toggle_favorite()` 支持 mastered↔favorite 双向切换
- `backend/app/api/mastered.py` — 新建，`GET /api/mastered` + `GET /api/mastered/types`
- `backend/app/api/learned.py` — 新增 `PATCH /learned/{word_id}/master` 端点
- `frontend/src/views/Mastered.vue` — 新建「已熟练」页面
- `frontend/src/router/index.ts` — 添加 `/mastered` 路由
- `frontend/src/App.vue` — 导航栏新增「已熟练」链接

### 3. SSE 行级流式输出

**问题**：单词生成是阻塞 HTTP GET，用户需等待 LLM 完全返回才能看到结果。

**方案**：新增 `GET /api/words/random/stream` SSE 端点，后端流式接收 LLM token → 解析完整 JSON → 逐行 yield 每个单词作为独立 SSE event。前端逐个展示词卡。

**关键实现**：
- `WordAgent.generate_words_stream()` — 累加 token → 一次性 JSON 解析 → 逐行 yield（比逐 token 渐进解析更可靠）
- `WordService.stream_random_words()` — 流式事件生成器（word/done/error）
- `streamRandomWords()` — 前端 SSE 读取 + 自动重试 1 次

### 4. 重试机制

**问题**：网络波动导致 LLM 调用/API 请求静默失败，用户体验差。

**方案**：分层重试策略

| 层级 | 位置 | 策略 |
|------|------|------|
| 前端 axios | `api/index.ts` | GET 2次 (0.5s/1s), POST 1次 (1s) |
| 前端 SSE | `streamRandomWords` | 连接失败重试 1次 (1s) |
| 后端 LLM | `BaseAgent._generate` | 2次 (1s/3s) |
| 后端 JSON | `WordAgent` | 解析失败重试 1次 |
| 后端工具 | `app/core/retry.py` | 3个预设装饰器 (quick/moderate/steady) |

### 5. Docker 容器化

**问题**：依赖环境复杂（Python + Node + MeCab + Redis），部署成本高。

**方案**：多阶段构建 + docker-compose 编排

- `Dockerfile` — Stage1 Node 构建前端，Stage2 Python 运行后端 + Serve 前端静态文件
- `docker-compose.yml` — App + Redis 服务编排
- 国内镜像源适配（DaoCloud 镜像替代已停用的阿里云加速器）
- 前端通过 `FRONTEND_DIST` 环境变量由 FastAPI 直接 Serve

### 6. Redis 本地缓存降级

**问题**：Redis 不可用时所有缓存功能失效。

**方案**：`RedisClient` 自动降级到 TTL-aware 本地内存缓存（`_LocalCache`）：

```python
_sync_get(key):
    try: return redis.get(key)
    except: return local_cache.get(key)
```

所有 `_sync_get/set/delete` 及 async 的 `get/set/delete` 均做了双重保障。

### 7. pykakasi 替换 MeCab + 在线升级/回退

**问题**：`mecab-ipadic-utf8` 词典 523MB，Docker 镜像臃肿。

**方案**：
- 默认使用 pykakasi（~10MB），覆盖 N5-N1 所有常用汉字
- 可选升级至 fugashi + unidic-lite（~50MB），生僻汉字更准
- **应用内升级**：点击「升级至 MeCab」→ SSE 流式显示 pip 安装进度
- **应用内回退**：点击「回退至 pykakasi」→ 强制切回 + 持久化偏好标记
- 偏好持久化：`data/.dict_preference` 文件，重启后依然生效

### 8. Bug 修复

| Bug | 原因 | 修复 |
|-----|------|------|
| 首页收藏后进详情页显示未收藏 | `WordDetail.vue` 硬编码 `is_favorited: false` | 通过 `store.clickedWordFavorited` 传递状态 |
| 详情页取消收藏，首页星标不同步 | `favoritedIds` 为 Home 局部变量 | 提至 Pinia store，详情页同步更新 |
| 详情页取消收藏实际未生效（DB 词） | `handleFavorite` 对 DB 词不传 ext | 始终传 ext |
| DB `ext` 字段被误用 | `toggle_favorite` 中 `Word(ext=ext)` | 移除该赋值，ext 留给未来生产使用 |
| `settings` 模块名冲突 | 新 API 模块名与 `app.core.config.settings` 冲突 | 重命名为 `dictionary` |
| 取消收藏的词不在已熟练列表 | 旧逻辑直接 `db.delete(fav)` | 改为 `fav.status = "mastered"` |

### 9. 向量存储修复 + 异步化

**问题**：文章向量存储经历了三次尝试才最终解决：

1. **首次尝试**：把 `store_vector` 放在 SSE 生成器的 `yield done` 之后 → 前端断开 SSE 连接后生成器被终止，代码不执行
2. **二次尝试**：后台线程，但线程创建放在 `yield` 之后 → 同样被终止
3. **三次尝试**：后台线程放在 `yield` 之前启动 → 但线程中闭包捕获的 `milvus_client` 有竞态问题

**最终方案**：
- SSE 生成器中，`store_vector` 在后台线程中运行，线程在 `yield done` **之前**启动
- 线程内重新 import `article_agent` 避免闭包竞态
- 前端立即收到 `done`，向量存储不阻塞用户体验

### 10. Milvus Lite 问题修复

**问题**：
- `pymilvus>=2.4.0` 不含 `milvus-lite` 嵌入式引擎，导致 `MilvusClient()` 只能连远程服务，本地文件模式报错
- `_setup_fallback()` 中 `_save_fallback()` 在 `_using_fallback = True` 之前调用，跳过了首次保存
- 集合创建后未调用 `load_collection()`，导致查询时报 `collection released` 错误
- Milvus 写入失败后没有动态降级，异常被吞

**修复**：
- `requirements.txt` 改为 `pymilvus[milvus_lite]>=2.4.0`
- `_setup_fallback()` 修复保存顺序
- 创建集合后调用 `load_collection()`
- `insert()` 增加动态降级：Milvus 写入失败 → 自动切到 numpy fallback，后续走文件存储

## 最终向量状态

Milvus Lite 正常运行（非 fallback），6 篇文章全部成功存入向量库：

| 文章 | ID | 状态 |
|------|----|------|
| 気をつけて！ | 1 | ✅ |
| 公園でのひととき | 2 | ✅ |
| 日本の天気と私の習慣 | 3 | ✅ |
| 健康を守る習慣 | 4 | ✅ |
| 毎日の習慣 | 5 | ✅ |
| 新しい生活の始まり | 6 | ✅ |

## 遗留问题

详见 [TODOS.md](TODOS.md)。

## 影响范围

| 模块 | 改动量 |
|------|--------|
| 后端 API | +3 文件（mastered/dictionary/retry） |
| 后端 Service | 大幅修改 word_service + japanese_util |
| 前端页面 | +1 文件（Mastered），大改 Home/App/WordDetail |
| 基础设施 | +4 文件（Dockerfile/compose/ignore/README） |
| 测试 | +3 文件（state_machine/api/concurrency），46 用例 |
| 镜像大小 | 1.33GB → 712MB（-600MB，去除 MeCab 词典） |
