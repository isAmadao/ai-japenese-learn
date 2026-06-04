# 003 · 后端框架 & LLM 集成

- **日期**: 2026-06-04
- **状态**: ✅ 已采纳

## 背景

需要一个 Python 后端框架提供 REST API，并集成 LangChain 调用大语言模型。

## 方案

| 组件 | 选型 | 原因 |
|------|------|------|
| Web 框架 | FastAPI | 自动 OpenAPI 文档、类型校验、高性能异步支持 |
| ORM | SQLAlchemy 2.0 | 成熟的声明式 ORM，支持同步/异步 |
| LLM 框架 | LangChain | 标准化 LLM 调用、prompt 管理、模型切换 |
| LLM 提供方 | Qwen (DashScope) | 国产模型，API 价格低，后续可热切换 |
| 服务端 | uvicorn | FastAPI 推荐 ASGI 服务器 |

## 架构演进

### v1.0: 直接调用

```
API → Service → LLM Service (ChatOpenAI) → Qwen API
```

### v1.1: Agent 系统（当前）

```
API → Service → Agent (BaseAgent) → LLM + Redis缓存 + Milvus向量库
```

Agent 层封装了 Redis 缓存、向量嵌入和 Milvus 持久化，Service 层专注于业务编排。

## 后果

- ✅ 模块划分清晰：API / Service / Agent 三层
- ✅ LangChain 的 `ChatOpenAI` 对 OpenAI 兼容 API 开箱即用
- ⚠️ FastAPI 的同步 Depend 机制 + StreamingResponse 的 Session 管理需要手动处理

## 关联

- [004 · LLM 供应商选择](004-llm-provider.md)
- [006 · Agent + Redis 缓存系统](006-agent-redis-cache.md)
