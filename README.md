# 🇯🇵 AI 日本語学習 — AI Japanese Learning

AI 驱动的日语学习应用，后端基于 Python FastAPI + LangChain，使用 Qwen 模型生成日语学习内容。前端基于 Vue 3 + TypeScript。

## 项目结构

```
ai-japenese-learn/
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── api/               # REST API 路由
│   │   ├── core/              # 配置、数据库、Redis、Milvus
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务逻辑（LLM、单词、文章）
│   │   └── main.py            # FastAPI 入口
│   ├── skills/                # (预留) 自定义技能
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/               # API 客户端
│   │   ├── stores/            # Pinia 状态管理
│   │   ├── views/             # 页面组件
│   │   ├── components/        # 公共组件
│   │   └── router/            # 路由配置
│   └── package.json
└── README.md
```

## 快速开始

### 前置条件

- Python 3.10+
- Node.js 18+
- npm 或 yarn
- （可选）Redis（用于 LLM 缓存，不配置也不影响核心功能）

### 1. 后端

**方式一：conda 虚拟环境（推荐，已创建）**

```bash
cd backend

# 激活现有 conda 环境
conda activate ai-japanese-learn

# （首次部署时）安装依赖
pip install -r requirements.txt

# 配置环境变量（复制模板并编辑）
cp .env.example .env
# 编辑 .env 文件，设置 LLM_API_KEY 等参数

# 启动服务
python -m uvicorn app.main:app --reload --port 8000
```

后端启动后访问：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端启动后访问: http://localhost:5173

### 快速启动（前后端同时）

需要两个终端窗口：

```bash
# 终端 1 — 后端
conda activate ai-japanese-learn
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 终端 2 — 前端
cd frontend
npm run dev
```

> 💡 Windows 用户注意：`conda activate` 在 PowerShell、CMD、Git Bash 中均可使用。如果提示命令找不到，请先运行 `conda init` 初始化 shell，或使用 `D:\miniconda3\Scripts\conda.exe activate ai-japanese-learn`。

### 3. Docker 部署（推荐）

#### 方式一：完整部署（含 Redis）

```bash
# Linux / Mac
export LLM_API_KEY=your_api_key_here

# Windows (PowerShell)
# $env:LLM_API_KEY = "your_api_key_here"

# 一键启动（构建镜像 + 启动 Redis + 启动应用）
docker compose up -d

# 访问 http://localhost:8000
# 查看日志
docker compose logs -f app
```

#### 方式二：仅应用（无需 Redis）

```bash
# 构建镜像
docker build -t ai-japanese-learn .

# Linux / Mac
docker run -d --name ai-learn -p 8000:8000 \
  -e LLM_API_KEY=your_key \
  -v ai_data:/app/data \
  ai-japanese-learn

# Windows (PowerShell)
# docker run -d --name ai-learn -p 8000:8000 `
#   -e LLM_API_KEY=your_key `
#   -v ai_data:/app/data `
#   ai-japanese-learn
```

#### 本地缓存 vs Redis

| 场景 | 有 Redis | 无 Redis（本地内存缓存） |
|------|---------|-----------------------|
| F5 刷新保持同批词 | ✅ | ✅（同进程内有效） |
| LLM 响应缓存 | ✅ | ✅ |
| 多实例扩展 | ✅ | ❌（每个实例独立缓存） |
| 容器重启后缓存保留 | ✅ | ❌（内存释放） |

> 单容器部署本地缓存完全够用。如需扩展或多实例，只需启动 Redis 容器并设置 `REDIS_HOST` 环境变量即可平滑切换。

### 4. 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `USE_SQLITE` | 使用 SQLite（否则用 MySQL） | `true` |
| `LLM_API_KEY` | Qwen API Key（开发阶段用，上线后请置空） | - |
| `LLM_API_BASE` | Qwen API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | Qwen 模型名 | `qwen-plus` |

> ⚠️ **上线前必读**：本项目设计为**用户自行提供 API Key**，在首页填写后仅保存在浏览器 localStorage 中。开发阶段可以在 `.env` 中设置 `LLM_API_KEY` 作为兜底。**上线到公网前，请务必将 `LLM_API_KEY` 置空**，否则用户即使不填写 Key 也能调用 LLM，导致你的账户产生费用。前端会在生成文章/换句子前检查 Key 是否已设置，未设置时给出提示引导用户去首页填写。

## 功能

- **首页**: 随机生成 5 个日语单词，可收藏、查看详情、朗读
- **单词详情**: 中日文对照、假名标注、例句、朗读、相关文章、配图
- **搜索**: 支持日语表记/假名/中文搜索（关键字 + 语义搜索）
- **图片搜索**: 上传图片自动识别日语文字并搜索相关单词
- **收藏页**: 分页展示收藏的单词（6列布局），支持生成文章
- **已学习/已熟练**: 学习进度追踪，标记单词学习状态
- **文章生成**: 选择收藏的单词 → 选 N5-N1 级别 → AI 生成短文
- **文章详情**: 中日双语对照、嵌入单词链接、朗读全文
- **智能配图**: CLIP 跨模态匹配最佳插图，支持 Pexels 图库
- **句子换新**: AI 重新生成例句，支持动漫/影视/日常等风格

## 技术栈

- **后端**: Python 3.12, FastAPI, SQLAlchemy, LangChain, Qwen API
- **数据库**: SQLite (开发) / MySQL (生产)
- **缓存**: Redis (LLM 结果缓存)
- **向量数据库**: Milvus Lite (内嵌, 本地文件)
- **前端**: Vue 3, TypeScript, Vite, Pinia, Vue Router
- **TTS**: Web Speech API + 日语语音包

## 项目技能

### `/install-japanese-tts`

安装 Windows 日语 TTS 语音包，解决浏览器用中文发音读日语的问题。

```bash
# 方式一：通过 Claude Code 技能
/install-japanese-tts

# 方式二：直接运行脚本
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/install-tts.ps1
```

安装后需重启浏览器。验证方法：
```javascript
// 浏览器控制台
speechSynthesis.getVoices().filter(v => v.lang.startsWith('ja'))
```

## 后续扩展

- [ ] LangChain Skills 自定义技能
- [ ] MCP (Model Context Protocol) 集成
- [ ] 用户认证系统
- [ ] Milvus 向量检索（语义搜索单词）
- [ ] Redis 缓存优化
- [ ] 单词学习进度追踪
- [ ] SRS 间隔重复记忆

## 📝 开发日志

项目所有技术决策、优化记录、问题排查和遗留事项统一记录在 [`docs/decisions/`](docs/decisions/) 目录：

| 文件 | 内容 |
|------|------|
| [SUMMARY.md](docs/decisions/SUMMARY.md) | 📊 架构全景 + 关键优化点速览 |
| [TODOS.md](docs/decisions/TODOS.md) | 📋 遗留问题 & 待办事项 |
| [001-database-selection.md](docs/decisions/001-database-selection.md) | 关系型数据库选型 |
| [002-vector-database-selection.md](docs/decisions/002-vector-database-selection.md) | 向量数据库选型 |
| [003-backend-framework.md](docs/decisions/003-backend-framework.md) | 后端框架 & LLM 集成 |
| [004-llm-provider.md](docs/decisions/004-llm-provider.md) | LLM 供应商选择 |
| [005-frontend-framework.md](docs/decisions/005-frontend-framework.md) | 前端框架 |
| [006-agent-redis-cache.md](docs/decisions/006-agent-redis-cache.md) | Agent + Redis 缓存系统 |
| [007-streaming-sse.md](docs/decisions/007-streaming-sse.md) | SSE 流式输出 |
| [008-containerization.md](docs/decisions/008-containerization.md) | 容器化方案 |

每条决策记录包含：**问题→方案→选型原因→优化效果→经验教训**，便于 AI 和开发者快速了解项目上下文。
