# 002 · 向量数据库选型

- **日期**: 2026-06-04
- **状态**: ✅ 已采纳

## 背景

项目需要存储单词和文章的向量嵌入，用于语义相似度搜索。最初需求指定使用 Milvus。

## 探索历程

### ❌ 方案一：标准 Milvus Server

```python
connections.connect(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
```

**问题**: 需要独立部署 Milvus 服务端，对开发者不友好。

### ❌ 方案二：Milvus Lite（pip install milvus-lite）

**问题**: 在 Windows + conda 环境下，pip 创建临时测试文件后无法删除
```
PermissionError: [WinError 5] 拒绝访问
'accesstest_deleteme_fishfingers_custard_*'
```

**根因**: Windows Defender 实时扫描锁定新文件，pip 的 `_test_writable_dir_win()` 中 `os.unlink()` 失败。

**修复**: 修改 conda 环境 pip 源码，用 try/except 包裹 unlink：
```python
try:
    os.unlink(file)
except PermissionError:
    pass  # Windows Defender 锁定，但目录确实可写
```

### ❌ 方案三：ChromaDB

尝试用 `conda install -c conda-forge chromadb` 安装，但依赖太重（protobuf、grpcio），下载超时。对本项目数据量（< 10K 向量）过于笨重。

### ✅ 方案四：Milvus Lite（最终方案）

**现状**: pip 补丁后成功安装 `milvus-lite`，使用 pymilvus 原生 `MilvusClient` 本地模式。

```python
from pymilvus import MilvusClient as NativeClient
client = NativeClient("./data/milvus.db")  # 单文件向量数据库
```

**自动降级**: 若 milvus-lite 未安装，自动降级到 numpy + JSON 文件存储。

## 后果

- ✅ 零外部服务依赖，单文件向量库
- ✅ 代码层面 API 与 pymilvus 一致，未来可平滑切换到集群版 Milvus
- ⚠️ pip 补丁在升级 pip 后会失效，需重新打补丁

## 遗留问题

- 重装 / 升级 pip 后需重新修改 `filesystem.py`
- Windows Defender 排除目录配置可根治文件锁

## 关联

- [006 · Agent + Redis 缓存系统](006-agent-redis-cache.md)
