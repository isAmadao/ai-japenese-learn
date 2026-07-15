# 开发日志 2026-06-06 (下) — 星露谷 UI + 技能系统 + 发音重叠修复

## 概述

全面改造前端 UI 为星露谷物语像素农场风格，搭建 Claude Code 技能系统，修复发音重叠 Bug。

## 改动明细

### 1. Claude Code 技能系统搭建

**新增技能：**

| 技能 | 来源 | 用途 |
|------|------|------|
| `skill-creator` | `.claude/skills/skill-creator.md` | 引导创建新 skill 的 meta-skill |
| `find-skills` | vercel-labs/skills | 用 `npx skills` 搜索和安装社区 skill |
| `frontend-design` | anthropics/skills (506K 安装) | 高设计质量前端界面生成 |
| `opsx:propose/apply/archive` | Fission-AI/OpenSpec v1.4.1 | 规范驱动开发工作流 |

**配套文件：**
- `CLAUDE.md` — 项目级别指令文件，每个会话自动加载，注册了所有自定义 skill 的触发条件
- `.claude/settings.local.json` — 权限白名单 + command-based skill 注册
- OpenSpec 在项目根生成了 `openspec/` 目录 + `.claude/skills/` 下 5 个 skill

### 2. 前端全面 UI 改造 — 星露谷物语风格

**设计体系：**

| 要素 | 之前 | 之后 |
|------|------|------|
| 背景色 | 纯白 `#f1faee` | 天空渐变 `#5090C0→#E8C898` |
| 卡片/UI | 圆角阴影卡片 | 木质像素边框 + inset 阴影 |
| 导航栏 | 白色底 + 蓝色下划线 | 木牌背景 + 金色装饰条 + 钉子 |
| 按钮 | 圆角现代风格 | Press Start 2P 像素字体 + step-start 按压感 |
| 字体 | 系统字体 | Zen Maru Gothic（可爱） + Press Start 2P（像素标题） |
| 颜色 | 红/蓝/白 | 草绿/暖棕/金黄/奶油色 |

**改动的文件：**
- `frontend/src/style.css` — 完全重写：CSS 变量 + 全局组件样式
- `frontend/src/App.vue` — 导航栏→木牌，词典按钮像素风格
- `frontend/src/views/Home.vue` — 欢迎区木框，文案"农场"主题
- `frontend/src/components/WordCard.vue` — 卡片像素边框+木质阴影
- `frontend/src/views/WordDetail.vue` — 详情页金色镶边+例句木框
- `frontend/src/views/Favorites.vue` — 像素选中框+按钮风格统一
- `frontend/src/views/Learned.vue` — 像素标签页+卡片统一
- `frontend/src/views/Mastered.vue` — 同上

### 3. 字体放大 + 对比度优化

**问题**：Press Start 2P 过小难以阅读。

**方案**：

| 元素 | 之前 | 之后 |
|------|------|------|
| body 字号 | 默认 16px | **17px**，行距 1.8 |
| 导航链接 | 0.85rem | **1rem**，加粗 700 |
| 单词卡片 | 1.3rem | **1.5rem** |
| 单词详情 | 2rem | **2.4rem** |
| 全部按钮 | `0.4-0.55rem` | **`0.55-0.8rem`** |
| 文字颜色 | `#3A2A1A` / `#6B5A4A` | **`#2A1A0A`** / **`#4A3A2A`** |

### 4. 发音重叠修复

**问题**：点击发音按钮有时两次发音，且重叠。

**根因**：`speech.ts` 中 `_speakLocal()` 用**固定 2 秒超时**判断浏览器是否正常工作。但朗读一个单词正常需要 1~2s，超时在发音未结束时触发 `done(false)` → 服务器 TTS 降级启动 → 两路音频同时播放。

**修复**：改用**智能检测**模式：
```
speak() → 等 400ms
  ├─ speechSynthesis.speaking === true  → 等 onend 自然结束（无超时）
  └─ speechSynthesis.speaking === false → 浏览器 stub，降级服务器
```

**改动的文件**：
- `frontend/src/utils/speech.ts` — 重写 `_speakLocal` 检测逻辑，移除固定 2s 超时

### 5. UI 布局修复

| 问题 | 修复 |
|------|------|
| 主页"播种新词"和右上角"生成新词"同时出现 | 无单词时右上角按钮隐藏，有单词时显示"换一批" |
| 已学习页 🔊 被"已熟练"按钮挤掉 | 🔊 挪到单词右侧（card-header） |
| 已熟练页 🔊 同上 | 同上 |

## 技术要点

### Stardew Valley 设计系统实现

**像素阴影技巧**：
```css
box-shadow:
  inset -3px -3px 0 var(--wood-dark),   /* 右下内阴影 → 凹陷感 */
  inset 3px 3px 0 var(--wood-light),    /* 左上内阴影 → 光照感 */
  2px 3px 0 rgba(60,40,20,0.1);         /* 外阴影 */
```
通过 `step-start` 过渡实现像素游戏瞬间切换的按压感。

**针对中文/日语可读性的字体搭配**：
- 标题：`Press Start 2P`（像素感，但字号需放大到 0.7rem+ 才可读）
- 正文：`Zen Maru Gothic`（圆体，支持中日文，可爱风格）

### 技能系统架构

```
CLAUDE.md（会话级指令，自动加载）
├── skill-creator       → 创建新 skill 的流程
├── find-skills          → npx skills 搜索
└── frontend-design      → 前端设计指南

.claude/settings.local.json（命令注册）
├── install-japanese-tts → PowerShell 安装 TTS

OpenSpec（独立 CLI 工具）
├── opsx:propose  → 需求提案
├── opsx:apply    → 需求落地
└── opsx:archive  → 需求归档
```

## 影响范围

| 模块 | 改动量 |
|------|--------|
| 前端全局样式 | 完全重写 style.css（~450 行） |
| 前端视图 | 修改 6 个 .vue 文件 |
| 前端语音 | 重写 speech.ts 检测逻辑 |
| 项目配置 | +CLAUDE.md, +.claude/skills/ 3 个 skill |
| 工具链 | +OpenSpec 工作流, +npx skills 集成 |
| 基础设施 | Docker 镜像重建 |
