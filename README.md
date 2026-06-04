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

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置 LLM_API_KEY 等参数

# 启动服务（默认使用 SQLite，开箱即用）
uvicorn app.main:app --reload --port 8000
```

后端启动后访问：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端启动后访问: http://localhost:5173

### 3. 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `USE_SQLITE` | 使用 SQLite（否则用 MySQL） | `true` |
| `LLM_API_KEY` | Qwen API Key | - |
| `LLM_API_BASE` | Qwen API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | Qwen 模型名 | `qwen-plus` |

## 功能

- **首页**: 随机生成 5 个日语单词，可收藏、查看详情、朗读
- **单词详情**: 中日文对照、假名标注、例句、朗读、相关文章
- **收藏页**: 分页展示收藏的单词（6列布局），支持生成文章
- **文章生成**: 选择收藏的单词 → 选 N5-N1 级别 → AI 生成短文
- **文章详情**: 中日双语对照、嵌入单词链接、朗读全文

## 技术栈

- **后端**: Python 3.10+, FastAPI, SQLAlchemy, LangChain, Qwen API
- **数据库**: SQLite (开发) / MySQL (生产)
- **缓存**: Redis (预留)
- **向量数据库**: Milvus (预留)
- **前端**: Vue 3, TypeScript, Vite, Pinia, Vue Router
- **TTS**: Web Speech API (浏览器端日语朗读)

## 后续扩展

- [ ] LangChain Skills 自定义技能
- [ ] MCP (Model Context Protocol) 集成
- [ ] 用户认证系统
- [ ] Milvus 向量检索（语义搜索单词）
- [ ] Redis 缓存优化
- [ ] 单词学习进度追踪
- [ ] SRS 间隔重复记忆
