# 007 · SSE 流式输出

- **日期**: 2026-06-04
- **状态**: ✅ 已采纳

## 问题

同步生成文章时，用户需要等待 LLM 完整输出（5-10s）才能在界面上看到结果。需要让用户看到逐字生成的过程。

## 方案

**SSE (Server-Sent Events) + 行级流式输出**。

### 架构

```
前端 fetch() → POST /api/articles/generate-stream
                  ↓
            StreamingResponse (text/event-stream)
                  ↓
            ArticleAgent.generate_article_stream()
                  ↓
            LLM.stream() → 逐 token → SSE → 前端
                  ↓ (生成完毕)
            parse JSON → 保存 DB → 向量存储 → done: {article_id}
```

### SSE 事件格式

```
data: {"type":"token","content":"{"}           ← 逐 token
data: {"type":"token","content":"\\"title\\":"}
data: {"type":"token","content":"私の一日"}
...
data: {"type":"done","article_id":1}            ← 完成
data: {"type":"error","message":"..."}           ← 错误
```

### 前端消费

使用 `fetch()` + `ReadableStream`，非 `EventSource`（需要 POST 方法）。

```typescript
const response = await fetch('/api/articles/generate-stream', {
  method: 'POST',
  body: JSON.stringify({ word_ids, level }),
})
const reader = response.body!.getReader()
// 逐 chunk 解码 → 解析 SSE → 更新 UI
```

## 优化效果

- **感知性能**: 用户看到文字逐字出现，不再感觉"卡死" 🚀
- **实际延迟**: 首 token 延迟 ~2s，后续实时
- **用户体验**: 增加"暗色终端"风格的流式窗口，带闪烁光标

## 经验教训

### 同步 DB + 异步 SSE 的 Session 管理

FastAPI 的 StreamingResponse 需要手动管理 DB Session（不能使用 `Depends(get_db)`，因为 generator 生命周期超出 endpoint 函数）：

```python
def event_stream():
    db = SessionLocal()  # 手动创建
    try:
        ...
    finally:
        db.close()       # 手动关闭

return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Stream 和 Cache 的矛盾

流式输出不能提前缓存（不知道完整内容），但非流式可以。同时保留两个端点：
- `POST /api/articles/generate` — 同步 + Redis 缓存（快速获取已有结果）
- `POST /api/articles/generate-stream` — 流式（实时展示生成过程）

## 关联

- [003 · 后端框架 & LLM 集成](003-backend-framework.md)
- [006 · Agent + Redis 缓存系统](006-agent-redis-cache.md)
