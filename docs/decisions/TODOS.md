# 遗留问题 & 待办事项

## 🔴 待解决

| 优先级 | 问题 | 分类 | 详情 | 关联 ADR |
|--------|------|------|------|----------|
| 高 | pip 文件锁补丁会随升级失效 | 环境 | 修改了 `conda env` 的 pip 源码 (`filesystem.py`)，下次 `pip install --upgrade pip` 会被覆盖。建议配置 Windows Defender 排除目录 | [002](002-vector-database-selection.md) |
| 高 | Qwen Embedding API 不可用 | 功能 | `text-embedding-v3` 通过 OpenAI 兼容端点调用超时，当前使用哈希向量降级。需确认 DashScope 的正确 Embedding endpoint 和模型名 | [004](004-llm-provider.md) |
| 中 | 单词"换一批"每次调 LLM → Token 消耗大 | 性能 | 当前方案是每次点换一批都调 LLM 生成新词，虽然解决了重复问题，但 Token 消耗增加。优化方向：预生成一批缓存起来 | [006](006-agent-redis-cache.md) |

## 🟡 待优化

| 优先级 | 优化点 | 分类 | 方案 |
|--------|--------|------|------|
| 中 | SSE 生成文章时不重新覆盖已有缓存 | 性能 | 流式生成完保存后，同步写入 Redis 缓存，下次同步请求直接命中 |
| 中 | 收藏页按级别筛选 | 功能 | 在级别选择弹窗中添加筛选功能，只显示目标级别的单词 |
| 中 | 单词详情页关联文章显示为"无"时隐藏区域 | UI | 空状态组件优化 |
| 低 | 前端错误提示统一化 | UX | 目前 error 处理分散在各组件，可以封装统一错误组件 |

## 🟢 待扩展

| 优先级 | 功能 | 分类 | 说明 |
|--------|------|------|------|
| 低 | LangChain Skills 自定义技能 | 架构 | 预留 `backend/app/skills/` 目录，用于定义日语学习专用 LangChain 工具 |
| 低 | MCP (Model Context Protocol) 集成 | 架构 | 预留接口，让 Claude Desktop 等 MCP 客户端能连接本项目 |
| 低 | 用户认证系统 | 功能 | 目前用 `default` 用户，后续可接入 JWT / OAuth |
| 低 | SRS 间隔重复记忆 | 功能 | 基于遗忘曲线的单词复习系统 |
| 低 | 单词学习进度追踪 | 功能 | 已学/待学/掌握单词统计 |
| 低 | Docker Compose 部署 | DevOps | 统一打包后端 + Redis + 前端 |

## 🔵 已解决（历史关键问题）

| 问题 | 解决方式 | 涉及文件 |
|------|----------|----------|
| `ModuleNotFoundError: No module named 'loguru'` | 替换为标准库 `logging` | `milvus_client.py` |
| `redis.asyncio` 不可用 | 条件导入 + 同步连接池降级 | `redis_client.py` |
| Vite `@/` 路径别名不识别 | 添加 `vite.config.ts` 的 `resolve.alias` | `vite.config.ts` |
| `article_words` 表名冲突 | 移除重复的 `ArticleWord` ORM 模型 | `models/article.py` |
| 首页单词不刷新 | 每次 `use_cache=False` 调 LLM 生成新词 | `word_service.py` |
| 朗读用中文发音 | 显式选择日语 TTS 语音 | `utils/speech.ts` |
| Milvus 安装失败 | pip 源码补丁 + 最终安装 Milvus Lite | `filesystem.py` |

## 标签索引

```
#环境问题  #功能缺失  #性能优化  #UI优化  #架构扩展  #已解决
```
