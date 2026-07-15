# 开发日志 2026-07-04 — 用户系统微服务化 + TTS 停止 + ES 单词搜索

## 概述

完成四大改动：① 用户认证系统从日语项目中独立为可复用微服务架构；② 离开页面自动停止 TTS 朗读；③ Elasticsearch 单词搜索（BM25 + 向量两路召回）；④ Docker 镜像更新。

---

## 1. 用户认证系统微服务化

### 背景

原认证系统嵌入在日语项目 `backend/app/core/auth.py` + `backend/app/api/auth.py` 中，与其他项目耦合（硬编码 import、共享数据库）。需要将其独立为可复用的认证方案。

### 架构产出

产出三个组件：

```
D:\AiLearn\myProject\
├── auth-service/                      ← 独立认证微服务
│   └── main.py                        ← FastAPI app, 独占用户 DB
│
├── auth-client/                       ← 客户端包（其他项目集成用）
│   ├── pyproject.toml
│   └── fastapi_auth_client/
│       └── client.py                  ← ~50 行，仅依赖 fastapi + python-jose
│
├── auth-kit/                          ← 完整认证功能包（日语项目在用）
│   └── fastapi_auth_kit/
│       ├── plugin.py                  ← AuthKit 主类（配置注入 + 依赖注入）
│       ├── core/                      ← JWT、密码哈希、CAPTCHA、邮件、重试
│       ├── models/user.py             ← User 模型工厂
│       ├── schemas/auth.py            ← Pydantic schema
│       └── api/auth.py + admin.py     ← 认证/用户管理路由
│
└── auth-kit-frontend/                 ← 前端认证组件包
    └── src/
        ├── stores/auth.ts             ← Pinia store
        ├── api/http.ts + auth.ts      ← Axios 拦截器 + API 调用
        ├── router/guard.ts            ← 路由守卫工厂
        └── components/                ← LoginForm + ForgotPassword
```

### 集成验证

| 宿主项目 | 技术栈 | 集成方式 | 状态 |
|---------|--------|---------|------|
| 日语学习 | FastAPI + 同步 SQLAlchemy | auth-kit 包替换原生 auth | ✅ |
| 多模态智能体 | FastAPI + 异步 SQLAlchemy | auth_setup.py（独立 sync DB） | ✅ |

### 微服务架构示意

```
┌──────────────────┐      JWT 令牌       ┌──────────────────┐
│  Auth Service     │◄───────────────────►│  日语学习项目     │
│  port:8080        │    本地验证         │  (不动代码)       │
│  独占用户 DB      │                     └──────────────────┘
└──────┬───────────┘
       │ JWT (本地验证)
       ▼
┌──────────────────┐
│  多模态智能体     │
│  (新增 auth-     │
│   client 包)     │
└──────────────────┘
```

---

## 2. TTS 停止（离开页面）

### 问题

`ArticleDetail.vue`、`WordDetail.vue` 等页面点击「🔊 朗读」后离开页面，音频继续播放。

### 修复

| 文件 | 改动 |
|------|------|
| `frontend/src/utils/speech.ts` | 🆕 新增 `stopSpeech()` 函数，同时取消浏览器语音合成 + 暂停 server audio |
| `frontend/src/views/ArticleDetail.vue` | 🔧 `onUnmounted` → `stopSpeech()` |
| `frontend/src/views/WordDetail.vue` | 🔧 `onUnmounted` → `stopSpeech()` |
| `frontend/src/views/Mastered.vue` | 🔧 `onUnmounted` → `stopSpeech()` |
| `frontend/src/views/Learned.vue` | 🔧 `onUnmounted` → `stopSpeech()` |

---

## 3. Elasticsearch 单词搜索

### 架构演进

```
改造前:                             改造后:
Redis session cache (随机词)          ES jp_words 索引 (14,307 词)
SQL LIKE 搜索 (无)                    BM25 全文搜索 (倒排索引)
                                    + 向量 KNN 语义搜索 (本地模型)
```

### 关键决策

1. **为什么用 ES 不用 Milvus**：ES 内置倒排索引 + dense_vector 混合搜索，一个索引解决所有问题，批量导入性能好
2. **为什么不用 Elasticsearch 默认分词**：安装 IK 中文分词器（`analysis-ik`），同时支持日语（standard 分词器）+ 中文释义搜索
3. **为什么本地模型用 `paraphrase-multilingual-MiniLM-L12-v2`**：384 维、50+ 语言支持、SOTA 句子向量质量
4. **为什么不用 `sentence-transformers` 做 Docker 部署**：PyTorch 依赖 ~2.5GB，fastembed ONNX 模型无法从国内镜像站下载（Xet 协议不支持）

### 最终方案

| 环境 | 搜索方案 | 原因 |
|------|---------|------|
| 本地开发 | BM25 + 向量 KNN | `sentence-transformers` + PyTorch 已安装 |
| Docker | BM25 全文搜索 | 无 ML 依赖，镜像 267MB |

### 改动清单

| 文件 | 改动 |
|------|------|
| `backend/app/core/milvus_client.py` | 🔧 嵌入维度 1024 → 384 |
| `backend/app/agent/base_agent.py` | 🆕 `warm_local_model()` + `_embed_local()` 本地模型 |
| `backend/app/agent/word_agent.py` | 🔧 `store_vector()` 返回 bool |
| `backend/app/services/word_service.py` | 🔧 `search_words()` 从 SQL LIKE → ES hybrid |
| `backend/app/api/words.py` | 🔧 搜索端点去掉 `api_key` 参数 |
| `backend/scripts/import_words_to_es.py` | 🆕 ES 批量导入脚本（500 条/批，关 refresh） |
| `backend/scripts/embed_all_words.py` | 🔧 添加 Milvus setup + 本地模型支持 |
| `backend/requirements.txt` | 🔧 +`elasticsearch`, +`fastembed` |
| `frontend/src/views/Search.vue` | 🆕 搜索页面（带防抖 + 结果卡片） |
| `frontend/src/api/index.ts` | 🆕 `searchWords()` API 调用 |
| `frontend/src/router/index.ts` | 🔧 +`/search` 路由 |
| `frontend/src/App.vue` | 🔧 导航栏+「🔍 搜索」链接 |

### 搜索效果

| 查询 | BM25 命中 | 结果 |
|------|----------|------|
| 「炊く」 | 1854 | 炊く、炊事、自炊、炊飯器、煮炊き |
| 「食べる」 | 1591 | 食べる、食べ物、並べる |
| 「学习」(中文) | 81 | 学校、学生、大学、中学、留学 |
| 「雨」 | 27 | 雨、梅雨、大雨、小雨、雨戸 |
| 「cat」 | 3 | カタログ、コミュニケーション、マスコミ |

响应时间：43ms - 258ms（BM25）

---

## 4. Docker 构建

| 文件 | 改动 |
|------|------|
| `Dockerfile` | 🔧 +auth-kit 复制步骤，简化依赖（BM25 搜索无需 ML 库） |
| `docker-compose.yml` | 🔧 +`hf_cache` volume（模型缓存持久化） |
| `backend/requirements.txt` | 🔧 +`elasticsearch`, +`fastembed`（带 ONNX 回退） |

最终镜像大小：**267MB**，构建时间 63-166s。

---

## 待解决问题

1. **Docker 向量搜索**：`fastembed` 的 ONNX 模型托管在 Qdrant 的 HuggingFace 仓库（使用 Xet LFS 存储），国内镜像站不支持，需有国际网络时下载
2. **词典嵌入**：14,307 词已导入 ES（带 384 维向量），但向量来自 sentence-transformers。如果将来切换到 fastembed，向量维度一致但数值不同，需重新导入
3. **IK 分词器**：日语用 standard 分词器按字符切分，对于「食べる」等词效果良好，但复合词（如「国際連合」）不能识别为整体。可考虑安装 `analysis-kuromoji` 插件提升日语分词精度
