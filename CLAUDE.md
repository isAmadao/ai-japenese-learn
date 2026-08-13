# AI Japanese Learning - Project Instructions

## 处理任务须知
处理任务时，先查看日志系统；简单任务简单处理，复杂任务分步处理，难处理的问题让开发者确认。

## 启动方式

前后端由开发者手动启动，Claude 不代为启动。

```bash
# 后端 (D:\AiLearn\myProject\ai-japenese-learn\backend)
conda activate ai-japanese-learn
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端 (D:\AiLearn\myProject\ai-japenese-learn\frontend)
cd frontend
npm run dev
```

## 基本开发规则

### 1. 功能边界控制
- **新增功能时**：严格控制改动范围，只影响目标功能，不影响已有功能
- **修改功能时**：仅修改当前功能涉及的代码，不波及无关模块

### 2. 测试流程
- 在本地项目（前端 dev server + 后端 API）中测试功能
- 使用 `admin / admin` 账号进行测试
- **不主动更新 Docker 镜像** — 只有开发者明确要求更新时才执行

### 3. 更新 Docker 镜像完整步骤
当开发者要求更新 Docker 时，按以下步骤执行（防止遗漏）：

```bash
# 项目根目录：D:\AiLearn\myProject\ai-japenese-learn

# 1. 如果改动了前端代码，重建 nginx（前端静态文件由 nginx 托管）
docker compose build --no-cache nginx
docker compose up -d nginx

# 2. 如果改动了后端代码，重建 app（Python 后端 + 前端 dist）
docker compose build --no-cache app
docker compose up -d app

# 3. 验证所有容器健康
docker compose ps
```

### 4. Git 提交策略
- **不自动提交 git** — Claude 生成完整代码后不主动 commit，不 `git add` / `git commit`
- 每次完整代码生成完成后，需**人工核验**：开发者验证功能无误后，再决定手动提交还是自动提交
- 设计文档 / 开发日志等中间产物同样遵循此规则，不自动提交

## Skills

### 创建新 Skill
当用户要求"创建新 skill"或"做一个新斜杠命令"时，按照 `.claude/skills/skill-creator.md` 中的流程执行。

### 安装日语 TTS
当用户需要安装日语语音包时，使用 `/install-japanese-tts` skill。

### 搜索/安装 Skills（Find Skills）
当用户问"有没有做 X 的 skill"、"帮我找个 skill"、"can you do X" 等时，按照 `.claude/skills/find-skills.md` 中的流程执行，使用 `npx skills` CLI 来搜索和安装。

### 前端设计（Frontend Design）
当用户要求构建 Web 组件、页面或应用时，按照 `.claude/skills/frontend-design.md` 中的设计思维和美学指南执行。避免通用 AI 审美，创造独特、生产级的前端界面。
