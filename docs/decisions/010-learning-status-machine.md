# 010 · 学习状态机 (favorite → learned)

- **日期**: 2026-06-05
- **状态**: ✅ 已采纳

## 问题

需要区分"已收藏待学习"和"已学习完成"两个阶段，在 UI 上分开展示。

## 方案

**在 Favorite 表加 status 字段，两状态共享同一关系表。**

```python
class Favorite(Base):
    __tablename__ = "favorites"
    ...
    status = Column(String(20), default="favorite")   # favorite | learned
    learned_at = Column(DateTime, nullable=True)
```

### 状态转换

```
收藏(favorite)  →  ✅已学习(learned)   单向，不可回退
```

### API

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/favorites?status=favorite` | 收藏列表（默认只显示 favorite） |
| `PATCH` | `/api/favorites/{id}/learn` | 标记为 learned |
| `GET` | `/api/learned?type=N5` | 已学习列表（按 type 筛选） |
| `GET` | `/api/learned/types` | 各 type 计数 |

### 前端

- 收藏页每个词卡下方新增 **✅ 已学习** 按钮
- 点击后该词从收藏页消失，出现在已学习页
- 已学习页按 N5-N1 标签页分页展示

## 备选方案

- **独立 Learned 表**: 增加复杂度，但历史记录更干净
- **删除 Favorite 记录 + 插入 Learned 记录**: 两表维护麻烦
- **单表加 status**: 🏆 最简单，ORM 层面共享关系查询

## 关联

- [005 · 前端框架](005-frontend-framework.md)
- [006 · Agent + Redis 缓存系统](006-agent-redis-cache.md)
