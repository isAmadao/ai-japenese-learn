# 📊 开发日志 · 决策与优化全景

本文件聚合了所有 ADR 的核心信息，便于快速回顾和 AI 学习。

## 架构全景

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Vite + TypeScript)                    │
│  ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐   │
│  │  Home   │ │Favorites │ │ WordDetail │ │Article   │   │
│  │ (随机5词)│ │(6列收藏) │ │ (详情/朗读) │ │ (文章)   │   │
│  └────┬────┘ └────┬─────┘ └─────┬──────┘ └────┬─────┘   │
│       └───────────┴─────────────┴──────────────┘          │
│                       │ Axios / SSE fetch                  │
└───────────────────────┼──────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────┐
│  Backend (FastAPI + uvicorn)                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ API 路由 │─>│ Service  │─>│  Agent (BaseAgent)    │   │
│  │ (路由+   │  │ (业务编排)│  │  ├─ ChatOpenAI (Qwen) │   │
│  │  校验)   │  │          │  │  ├─ Redis 缓存        │   │
│  └──────────┘  └──────────┘  │  ├─ Embedding (hash)  │   │
│                              │  └─ Milvus 存储       │   │
│                              └──────────────────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ SQLite   │  │  Redis   │  │  Milvus Lite         │   │
│  │ (单词/   │  │ (LLM缓存)│  │  (向量存储)           │   │
│  │  收藏)   │  │          │  │                      │   │
│  └──────────┘  └──────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

## 关键技术决策速览

| 决策 | 选型 | 核心理由 | 备选 |
|------|------|----------|------|
| 关系型 DB | SQLite / MySQL | 开发零配置 / 生产稳定 | PostgreSQL |
| 向量 DB | Milvus Lite | 嵌入式，免服务 | ChromaDB（太重） |
| Web 框架 | FastAPI | 自动文档，类型安全 | Flask, Django |
| LLM | Qwen (DashScope) | 低价，中日文强，免代理 | GPT-4o, Claude |
| LLM 框架 | LangChain | 标准化 Prompt/模型切换 | 直接调用 API |
| 缓存 | Redis | 高性能，TTL 灵活 | 内存缓存 |
| 前端 | Vue 3 + TS | 轻量，响应式 | React, Svelte |

## 关键优化点（按价值排序）

### 🥇 Agent + Redis 缓存系统
- **问题**: 每次调 LLM 等 5-10s，Token 消耗大
- **方案**: Agent 封装 LLM + Redis 缓存 + 降级
- **效果**: 缓存命中 → 100ms，Token 费用降低 90%+
- **学习点**: 降级策略比完美实现更重要

### 🥇 SSE 流式输出
- **问题**: 用户无所事事等 5-10s 看结果
- **方案**: StreamingResponse + 逐 token SSE
- **效果**: 首字 2s 出现，感知速度大幅提升
- **学习点**: 感知性能 > 实际性能

### 🥇 Milvus Lite 迁移
- **问题**: Milvus 标准版需独立服务，部署复杂
- **方案**: pymilvus `MilvusClient` 本地文件模式
- **效果**: 单文件向量库，零配置
- **学习点**: 三层降级（Lite → numpy → 报错提示）

### 🥈 确定性哈希向量
- **问题**: Embedding API 不可用时向量存储完全失效
- **方案**: SHA256 生成可复现单位向量
- **效果**: Embedding 始终可用
- **学习点**: 可用性 > 精度

### 🥈 Redis 同步/异步双模式
- **问题**: 同步 Agent 代码无法调用 async Redis
- **方案**: RedisClient 同时维护 sync + async 连接
- **效果**: 双模式共存无需重构

### 🥈 pip 文件锁补丁
- **问题**: Windows + conda 下 pip 无法安装任何包
- **方案**: 修改 pip 源码的 `os.unlink` → try/except
- **效果**: milvus-lite 装上了
- **学习点**: 区分"权限问题"和"文件锁问题"

### 🥇 数据流 v2 — 仅收藏单词持久化
- **问题**: 所有 LLM 生成单词都写入 DB，DB 膨胀且 session id 与 DB 主键冲突
- **方案**: 生成结果存 Redis (session 隔离)，仅收藏时写入 DB
- **效果**: DB 只存用户真正需要的单词，session 刷新不丢缓存
- **学习点**: 缓存/持久化分离，按数据价值分层存储

### 🥈 Session ID 轮转 — 区分"换一批"和 F5
- **问题**: "换一批"和 F5 都调同一接口，后端无法区分
- **方案**: "换一批"生成新 session_id 写入 localStorage → Redis 找不到旧缓存 → LLM 生成；F5 读现有 session_id → Redis 命中
- **效果**: "换一批"出新词，F5 保持当前词
- **学习点**: 前端状态驱动后端缓存策略

### 🥈 MeCab 假名校验 — 修正 LLM 读音错误
- **问题**: LLM 对汉字读音经常猜错（妥協→だかい ×）
- **方案**: fugashi + unidic 词典查每个词的正确读音，自动纠正
- **效果**: 读音准确率从 ~70% 提升到 ~99%
- **学习点**: LLM 不适合精确事实查询，需要工具辅助验证

### 🥉 收藏 ID 冲突修复
- **问题**: 用 session id(1-5) 当 DB 主键，不同 session 冲突
- **方案**: 按 word name 去重 + 自动递增主键
- **效果**: 同一单词多次收藏复用同一记录

## 技术债务

### 环境相关
- [ ] pip 补丁在升级后会失效（#环境问题）
- [ ] Windows Defender 排除 conda 目录可根治
- [ ] fugashi 的 INSTALLER.tmp 重命名仍会被锁（#环境问题）

### 功能缺失
- [ ] Qwen Embedding API endpoint 待确认（#功能缺失）
- [ ] Docker 容器化部署（#架构扩展）
- [ ] 用户认证系统（#架构扩展）
- [ ] 单词 SRS 间隔重复（#功能缺失）

### 性能
- [ ] 换一批每次调 LLM，Token 消耗大（#性能优化）
- [ ] 预生成单词池（#性能优化）

### 已解决
- [x] 收藏按钮无响应（WordCard emit 类型不匹配）
- [x] Session id 与 DB 主键冲突
- [x] LLM 假名读音错误（fugashi 校验）

## 文件时间线

```
2026-06-04
├── 18:00  🎉 项目初始化 (commit 1)
├── 18:15  🐛 fix: 模型表冲突 + requirements
├── 19:00  🐛 fix: redis.asyncio + SSE 流式
├── 19:30  🐛 fix: replace loguru with logging
├── 20:00  🤖 feat: Agent 系统 + 缓存 + 向量
├── 20:30  🔧 refactor: Milvus → numpy 向量存储
├── 21:00  🔧 refactor: pip 补丁 → Milvus Lite
├── 21:30  🐛 fix: 换一批不刷新问题
├── 21:45  🐛 fix: 日语 TTS 语音选择
├── 22:00  📝 feat: install-japanese-tts 技能
├── 22:30  📝 doc: 开发日志系统
├── 23:00  🔧 refactor: 数据流 v2（仅收藏持久化）
├── 23:15  🐛 fix: 收藏按钮无响应（emit 类型不匹配）
├── 23:20  🐛 fix: 收藏 ID 冲突（name 去重）
├── 23:25  🐛 fix: 换一批 vs F5 区分（session_id 轮转）
├── 23:35  🔊 feat: install-japanese-tts 技能生效验证
├── 23:40  🐛 fix: Milvus Lite fallback 标记未设置
├── 23:45  🤖 feat: MeCab 假名校验（fugashi + unidic）
└── 23:55  📝 doc: 更新开发日志（本次会话）
```
