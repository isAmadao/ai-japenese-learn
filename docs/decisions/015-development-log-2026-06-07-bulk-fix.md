# 开发日志 2026-06-07 — 批量修复遗留问题

## 概述

集中解决项目遗留的 5 个高/中优先级问题，涉及环境修复、API 调用优化、性能优化三个维度。

## 改动明细

### 1. pip 文件锁补丁随升级失效

| 问题 | 方案 | 文件 |
|------|------|------|
| pip 的 `_test_writable_dir_win()` 中 `os.unlink()` 被 Windows Defender 拦截，手动修改 pip 源码后升级被覆盖 | 创建 `scripts/fix-pip-lock.py` 一键修复脚本，支持 `--status / --undo / --defender` | `scripts/fix-pip-lock.py`, `.bat`, `-admin.bat` |

**关键发现**：MINGW64 下 PowerShell `Start-Process -Verb RunAs` 无法弹出 UAC 弹窗。改用 Python `ctypes.ShellExecuteExW` + `runas` 动词成功提权。

### 2. Qwen Embedding API 不可用

| 问题 | 方案 | 文件 |
|------|------|------|
| `langchain_openai.OpenAIEmbeddings` 调 DashScope `/compatible-mode/v1` 超时，全程走哈希降级 | 移除 `OpenAIEmbeddings`，改用 `httpx` 直连 DashScope OpenAI 兼容端点 `/v1/embeddings` | `base_agent.py` |

**实测结果**：`POST /v1/embeddings` → `text-embedding-v3` 返回 dim=1024 真实向量。

**影响**：之前存 Milvus 的向量是 SHA256 伪向量（无语义），现在是 DashScope 真实语义向量。

### 3. Milvus Lite 文件锁残留

| 问题 | 方案 | 文件 |
|------|------|------|
| 进程崩溃后 `data/milvus.db/LOCK` 残留，下次启动 Milvus 失败 | 启动时自动删 LOCK + `atexit.register(disconnect)` 安全关闭 | `milvus_client.py` |

**三层防护**：
- 启动删 LOCK（主动清理）
- atexit 注册（确保退出时关闭）
- numpy 降级（终极兜底）

### 4. "换一批"每次调 LLM → Token 消耗大

| 问题 | 方案 | 文件 |
|------|------|------|
| 每次换一批生成新 UUID → Redis MISS → 调 LLM 生成 7 个词 | Redis 词池预生成 25 词，分批取用 | `word_service.py`, `redis_client.py` |

**数据流**：
```
第一次: LLM 生成 27 词 → 池存 25 → 返回 5
第2-5次: Redis LPOP 5 → 秒回 (零 LLM)
第6次:  池空 → 再调 LLM → 池存 25 → 返回 5
```

**新增 Redis 操作**：`_sync_llen` / `_sync_lpop` / `_sync_rpush`

### 5. fugashi INSTALLER.tmp 文件锁

| 问题 | 方案 | 文件 |
|------|------|------|
| Windows Defender 锁定 pip 的 INSTALLER.tmp，无法改名 | `upgrade_to_mecab_stream()` 安装失败后自动扫描 site-packages 修复 INSTALLER.tmp | `japanese_util.py` |

## 全部改动的文件

| 文件 | 改动 |
|------|------|
| `scripts/fix-pip-lock.py` | 🆕 pip 文件锁一键修复脚本 |
| `scripts/fix-pip-lock.bat` | 🆕 批处理包装器 |
| `scripts/fix-pip-lock-admin.bat` | 🆕 管理员双击模式 |
| `scripts/pip_restore_and_patch.py` | 🆕 独立恢复+打补丁（备用） |
| `backend/app/agent/base_agent.py` | 🔧 Embedding 改用 httpx 直连 DashScope |
| `backend/app/core/milvus_client.py` | 🔧 启动删 LOCK + atexit 安全关闭 |
| `backend/app/core/redis_client.py` | 🔧 新增列表操作 `llen / lpop / rpush` |
| `backend/app/services/word_service.py` | 🔧 Redis 词池预生成机制 |
| `backend/app/services/japanese_util.py` | 🔧 INSTALLER.tmp 自动修复 |
| `docs/decisions/TODOS.md` | 📝 更新任务全景 |
| `docs/decisions/004-llm-provider.md` | 📝 更新 Embedding 状态 |

## 影响范围

- **后端**: Agent 系统、Milvus/Redis 基础设施、单词服务、日语工具 → 需重启
- **前端**: 无改动（Home.vue 等仍正常工作）
- **环境**: 新增 `scripts/` 下的修复脚本
