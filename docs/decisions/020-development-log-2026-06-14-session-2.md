# 开发日志 2026-06-14 — API Key 提取 + 内容风格选择 + Pexels 配图 + 批量 Bug 修复 + Docker 打包

## 概述

将 LLM API Key 从服务器配置提取到前端，用户首页自行填写；增加文章/句子的内容类型和风格选择；集成 Pexels 配图（手动生成/换图）；批量修复 16 个遗留问题；Docker 打包上线。

## 改动明细

### 1. 🔑 API Key 提取到前端

| 文件 | 说明 |
|------|------|
| `backend/app/agent/base_agent.py` | 🔧 `__init__` 接受 `api_key`，`_generate`/`_generate_stream` 支持运行时覆盖 |
| `backend/app/agent/word_agent.py` | 🔧 `generate_words`/`enrich_sentences` 增加 `api_key` 参数 |
| `backend/app/agent/article_agent.py` | 🔧 `generate_article`/`generate_article_stream` 增加 `api_key` 参数 |
| `backend/app/schemas/article.py` | 🔧 `ArticleGenerateRequest` 增加 `api_key` 字段 |
| `frontend/src/api/index.ts` | 🆕 `getApiKey()`/`setApiKey()`/`hasApiKey()` 工具函数 |
| `frontend/src/views/Home.vue` | 🆕 API Key 输入卡片（LLM + Pexels + 指引链接） |
| `frontend/src/views/Favorites.vue` | 🔧 生成文章前检查 API Key |
| `frontend/src/views/WordDetail.vue` | 🔧 句子换新前检查 API Key |
| `README.md` | 🔧 上线前 `LLM_API_KEY` 置空提醒 |

### 2. 🎨 内容类型 & 风格选择

| 文件 | 说明 |
|------|------|
| `backend/app/agent/article_agent.py` | 🆕 `_build_style_instruction()` — 拼接内容类型/风格/参考来源到 prompt |
| `backend/app/agent/word_agent.py` | 🔧 `enrich_sentences()` 增加内容类型/风格/来源参数 |
| `backend/app/schemas/article.py` | 🔧 `ArticleGenerateRequest` 增加 `content_type`/`style`/`source` |
| `frontend/src/views/Favorites.vue` | 🆕 弹窗增加内容类型（动漫/日剧/歌曲）和风格（感情/搞笑/冒险/史诗/朴素等）选择 + 来源输入 |
| `frontend/src/views/WordDetail.vue` | 🆕 句子换新展开选项面板，支持类型/风格/来源 |

### 3. 📸 Pexels 配图系统

| 文件 | 说明 |
|------|------|
| `backend/app/services/image_service.py` | 🆕 Pexels API 封装（搜索/随机选图/后台线程/同步保存） |
| `backend/app/models/article.py` | 🔧 `Article` 表新增 `image_url` 列 |
| `backend/app/models/word.py` | 🔧 `Word` 表新增 `image_url` 列 + `to_dict()` 暴露 |
| `backend/app/schemas/article.py` | 🔧 `ArticleResponse` 增加 `image_url` |
| `backend/app/schemas/word.py` | 🔧 `WordResponse` 增加 `image_url` |
| `backend/app/api/words.py` | 🆕 `POST /api/words/{id}/image` 生成/换单词配图 |
| `backend/app/api/articles.py` | 🆕 `POST /api/articles/{id}/image` 生成/换文章配图 |
| `backend/app/services/article_service.py` | 🔧 生成文章后异步搜图 |
| `backend/app/core/database.py` | 🔧 `_ensure_columns()` 迁移增加 `image_url` 列 |
| `frontend/src/views/WordDetail.vue` | 🆕 单词配图区域 + 「生成配图」/「换一张」按钮 |
| `frontend/src/views/ArticleDetail.vue` | 🆕 文章配图 + 「换一张」按钮 |
| `frontend/src/views/Home.vue` | 🆕 Pexels API Key 输入和指引 |

Pexels API 免费层 200 次/小时，个人使用足够。图片搜索在 Pexels 返回的 8 张结果中随机选一张（排除当前图片），确保「换一张」能换到不同图片。

### 4. 🐛 批量 Bug 修复

| # | 问题 | 修复 |
|---|------|------|
| 1 | Refresh token 队列重放错误 | 每个请求存储自己的 config，刷新后用各自的 config 重放 |
| 2 | `check-email` 永远返回 true | 改为真实数据库查询 |
| 3 | 文章接口无鉴权 | 三个文章端点加上 `get_current_user` 依赖 |
| 4 | 分页无加载态 | Favorites/Learned/Mastered 增加 loading-overlay |
| 5 | 旧注册接口无防护 | 删除无邮箱验证的 `POST /api/auth/register` |
| 6 | TTS blob URL 泄漏 | 设置新 URL 前先 revoke 上一个 |
| 7 | SSE 不走 axios auth | 增加 `_ensureAuthToken()` 预刷新 token |
| 8 | 找回密码暴露邮箱 | 无论邮箱是否存在都返回成功 |
| 9 | 静默吞错误 | Learned/Mastered 操作失败时显示错误提示 |
| 10 | `db_id` 未暴露给前端 | `types/index.ts` 增加 `db_id` 字段 |
| 11 | 管理端 N+1 查询 | 改为两次批量 GROUP BY |
| 12 | 词典升级 SSE 无重试 | 增加 2 次重试 + token 预刷新 |
| 13 | Learned/Mastered 没例句 | 卡片中显示第一条例句 |
| 14 | 忘记密码计时器未清理 | `Login.vue` 增加 `onUnmounted` 清理 |
| 15 | 朗读全文按钮溢出 | 改为 `width: auto` 自适应 |

### 5. 🐳 Docker 打包部署

- `Dockerfile` — 多阶段构建（Vue build → Python runtime）
- `nginx/Dockerfile` — Nginx 反向代理 + 前端托管
- `docker-compose.yml` — 3 服务：nginx + app + redis
- 修复 nginx healthcheck IPv6 问题
- 修复 nginx proxy_pass resolver 导致 502 的问题

### 6. 🗺️ 后续 MCP 方向

记录在 `docs/decisions/019-mcp-integrations.md`，Pexels（已实现）、Bing Search（已移除，国内访问不稳定）、高级 TTS、记忆插图等。

## 验证

- [x] 首页 API Key 设置 + 保存到 localStorage
- [x] 生成文章/句子传递 API Key
- [x] 内容类型（动漫/日剧/歌曲）和风格选择
- [x] 文章自动配图 + 换一张
- [x] 单词手动生成配图 + 换一张
- [x] 无 Key 时提示引导
- [x] Docker 三容器健康运行
- [x] 所有遗留问题已修复或移至待扩展
