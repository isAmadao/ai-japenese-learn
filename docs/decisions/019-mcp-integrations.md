# ADR 019: MCP 工具集成 — Pexels 配图 + Brave Search 真实例句

## 问题

日语学习 App 的文章缺乏视觉吸引力，例句全部依赖 LLM 生成——语法正确但有时不够自然。

## 方案

通过 REST API 封装外部服务（后续可切换为 MCP Server），为 App 增加两个增强功能：

1. **Pexels 图片搜索** — 文章生成后自动配图
2. **Brave Search 真实例句** — 从真实日文网页提取例句

## 改动明细

### 1. Pexels 自动配图

| 文件 | 说明 |
|------|------|
| `backend/app/services/image_service.py` | 🆕 Pexels API 封装 — 根据关键词搜索图片，返回首张图片 URL |
| `backend/app/models/article.py` | 🔧 Article 表新增 `image_url` 字段 |
| `backend/app/schemas/article.py` | 🔧 ArticleResponse 暴露 `image_url` |
| `backend/app/services/article_service.py` | 🔧 生成文章后调用 Pexels 搜索配图 |
| `backend/app/core/config.py` | 🔧 新增 `PEXELS_API_KEY` 配置项 |
| `frontend/src/views/ArticleDetail.vue` | 🔧 展示文章配图 |
| `frontend/src/types/index.ts` | 🔧 Article 类型新增 `image_url` |

**流程：**
1. LLM 生成文章 → 存 DB
2. 提取文章日文标题作为关键词
3. 调用 Pexels API 搜索相关图片
4. 首张图片 URL 存到 `Article.image_url`
5. 前端展示

**费用：** Pexels API 免费（每小时 200 次请求，足够个人使用）

### 2. Bing Search 真实例句

| 文件 | 说明 |
|------|------|
| `backend/app/services/search_service.py` | 🆕 Bing Web Search API 封装 — 搜索日文网站，提取含目标词的句子片段 |
| `backend/app/api/words.py` | 🔧 新增 `GET /api/words/{id}/real-examples` 端点 |
| `backend/app/core/config.py` | 🔧 新增 `BING_SEARCH_API_KEY` 配置项 |
| `frontend/src/api/index.ts` | 🔧 新增 `fetchRealExamples()` API 函数 |
| `frontend/src/views/WordDetail.vue` | 🔧 新增"真实例句"按钮和展示区 |

**流程：**
1. 单词详情页新增"🌐 真实例句"按钮
2. 调用后端 → Bing Web Search 日文网站
3. 提取包含该单词的句子片段
4. 前端展示来源 URL + 例句

**费用：** Bing Search 免费层 1,000 次/月，国内直接访问

> **注：** 之前用的是 Brave Search，外网有时不稳定。已替换为 Bing Search API（国内可直连，Azure Portal 申请免费 Key）。

### 3. 其他 MCP 方向（已记录，待扩展）

| 方向 | MCP/工具 | 说明 |
|------|----------|------|
| 🟡 高级 TTS | ElevenLabs | 比浏览器原生日语发音更自然 |
| 🟡 学习统计 | ECharts / 图表库 | 学习量 + 复习趋势 + 薄弱词分布 |
| 🔵 记忆图片 | Stability AI / DALL-E | 为每个单词生成记忆插图 |
| 🔵 视频素材 | YouTube Transcript | 从日语视频提取字幕做学习素材 |
| 🔵 词典叠加 | Jisho API | 叠加真实词典释义 |

## 配置

```bash
# .env
PEXELS_API_KEY=your_pexels_api_key
BRAVE_API_KEY=your_brave_search_api_key
```

## 验证

- [ ] 生成文章后自动显示配图
- [ ] 单词详情页可搜索真实例句
- [ ] 图片和例句有合适的兜底状态（空/加载/错误）
