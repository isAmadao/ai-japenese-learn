# 006 · Agent + Redis 缓存系统

- **日期**: 2026-06-04
- **状态**: ✅ 已采纳

## 问题

每次请求都调用 LLM 生成单词/文章，导致：
1. 响应时间 5-10s，用户体验差
2. Token 消耗大，API 费用高
3. 相同参数（如同一组单词生成文章）重复请求浪费

## 方案

**三层架构：Agent 层封装 LLM 调用 + Redis 缓存 + 降级策略**

```
API → Service → Agent (BaseAgent)
                     ├─ LLM 调用（LangChain ChatOpenAI）
                     ├─ Redis 缓存（_make_cache_key → _sync_get/_sync_set）
                     ├─ 向量嵌入（API 优先 → hash fallback）
                     └─ Milvus 持久化
```

### 缓存策略 (v1 → v2 演进)

**v1 (初始)**: LLM 生成 → 写入 DB → Redis 缓存 prompt 结果  
**v2 (当前)**: LLM 生成 → Redis session 缓存 → **仅收藏时写入 DB**

| 数据类型 | 缓存 Key | TTL | 说明 |
|----------|----------|-----|------|
| 随机单词 (v1) | `agent:llm:{sha256(prompt)}` | 1h | 已废弃 |
| 随机单词 (v2) | `session_words:{session_id}` | 1h | session 隔离，F5 不走 LLM |
| 文章生成 | `agent:llm:{sha256(words+level)}` | 2h | 相同单词+级别复用 |
| 单词向量 | 不缓存 | — | 直接写入 Milvus |

**v2 变更原因**:  
- v1 把所有单词都持久化到 DB，DB 膨胀且 session id(1-5) 与 DB 主键冲突  
- v2 改为 Redis session 缓存，前端 localStorage 存 session_id  
- "换一批" 轮转 session_id → Redis 未命中 → LLM 生成  
- F5 读现有 session_id → Redis 命中 → 同批单词

### 降级策略

| 组件 | 降级行为 | 代码位置 |
|------|----------|----------|
| Embedding API | → 确定性哈希向量 (`_make_deterministic_vector`) | `base_agent.py` |
| Milvus | → numpy/JSON 文件存储 | `milvus_client.py` |
| Redis | → 跳过缓存，返回 None | `redis_client.py` |

## 优化效果

- **缓存命中**: 响应时间从 5-10s 降至 ~100ms 🚀
- **Token 节省**: 相同内容不再重复生成，费用大幅降低
- **调用 LLM 生成新词**: ~5-8s（无法避免，但已最小化）

## 经验教训

### 1. Redis 同步缓存的设计

Agent 层使用同步 SQLAlchemy，不能直接使用 async Redis。解决方案：
- 在 `RedisClient` 中额外维护一个同步连接池 `_sync_pool`
- Agent 调用 `_sync_get / _sync_set` 方法
- 异步代码（FastAPI lifespan）使用 async 客户端

```python
class RedisClient:
    @property
    def _sync(self) -> sync_redis.Redis:
        if self._sync_pool is None:
            self._sync_pool = sync_redis.ConnectionPool(...)
        return sync_redis.Redis(connection_pool=self._sync_pool)
```

### 2. 确定性哈希向量的价值

当 Embedding API 不可用时，用 SHA256 生成可复现向量：

```python
@staticmethod
def _make_deterministic_vector(text: str, dim: int = 1024) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec = [(h[i % len(h)] ^ h[(i+1) % len(h)] ^ h[(i*7) % len(h)] - 127) / 128.0
           for i in range(dim)]
    # 归一化
```

**同一文本永远映射到同一向量**，语义搜索功能保持一致。

## 关联

- [003 · 后端框架 & LLM 集成](003-backend-framework.md)
- [007 · SSE 流式输出](007-streaming-sse.md)
