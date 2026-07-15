# 004 · LLM 供应商选择

- **日期**: 2026-06-04
- **状态**: ✅ 已采纳

## 背景

项目需要 LLM 生成日语单词、例句和文章。要求 API 价格低、中日文能力强。

## 方案

**Qwen 通义千问（DashScope）**。

### 选型原因

| 因素 | Qwen | OpenAI | Claude |
|------|------|--------|--------|
| 价格 | 🏆 极低 | ❌ 较高 | ❌ 最高 |
| 中日文 | 🏆 原生支持 | ✅ 优秀 | ✅ 优秀 |
| API 兼容 | 🏆 OpenAI 兼容 | — | — |
| 国内访问 | 🏆 无限制 | ❌ 需要代理 | ❌ 需要代理 |

### 配置

```bash
LLM_API_KEY=sk-...
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

通过 OpenAI 兼容 API (`langchain_openai.ChatOpenAI`) 调用，切换模型只需改环境变量。

## 备选方案

- **GPT-4o**: 质量好但价格高，国内需代理
- **Claude 3.5 Sonnet**: 质量好但价格高，国内需代理
- **本地 Ollama**: 无 API 费用但需要 GPU 资源

## 后果

- ✅ 通过标准 OpenAI 接口调用，切换零成本
- ✅ 已提供 API Key，开箱即用
- ⚠️ Embedding API（text-embedding-v3）曾因 langchain 路由问题超时，已修复为 httpx 直连

## 遗留问题

- ✅ 已修复: Embedding 改用 httpx 直接调用 OpenAI 兼容端点 `/v1/embeddings`，text-embedding-v3 正常可用

## 关联

- [003 · 后端框架 & LLM 集成](003-backend-framework.md)
