# 开发日志 2026-06-06 — 局域网部署 + 手机发音修复 + gRPC 优化

## 概述

部署到局域网、修复手机浏览器发音功能、解决 Milvus Lite gRPC 日志污染。

## 改动明细

### 1. 局域网部署

**问题**：项目仅在 localhost 可访问，无法在局域网其他设备（手机、平板）上使用。

**方案**：
- CORS 在 Docker 生产模式下自动允许所有来源（`allow_origins=["*"]`）
- 添加 Windows 防火墙入站规则放行 8000 端口
- 保持 Docker Compose 已有 0.0.0.0 绑定不变

**改动的文件**：
- `backend/app/main.py` — CORS 动态配置：`FRONTEND_DIST` 时 `["*"]`, 否则 localhost 白名单

### 2. Milvus Lite gRPC "too_many_pings" + "Invalid HTTP request" 修复

**问题**：启动后日志持续输出 `WARNING: Invalid HTTP request received.`，同时 Milvus Lite 内部报 `too_many_pings`。

**根因**：pymilvus 默认 gRPC keepalive ping 间隔为 **10ms**（过于激进），导致嵌入式 Milvus Lite 服务端发送 GOAWAY。连接断开后残留的 TCP 数据被 uvicorn 当作 HTTP 请求解析失败。

**修复**：在导入 pymilvus 前设置 gRPC 环境变量：

| 变量 | 值 | 说明 |
|------|-----|------|
| `GRPC_ARG_KEEPALIVE_TIME_MS` | 300000 (5min) | 心跳间隔从 10ms → 5 分钟 |
| `GRPC_ARG_HTTP2_MIN_SENT_PING_INTERVAL_WITHOUT_DATA_MS` | 300000 (5min) | 无数据时的最小 ping 间隔 |
| `GRPC_ARG_KEEPALIVE_TIMEOUT_MS` | 20000 (20s) | 心跳超时时间 |
| `GRPC_ARG_HTTP2_MAX_PINGS_WITHOUT_DATA` | 0 | 允许无数据时的 ping 次数（无限制） |

**关键点**：必须使用 `os.environ.setdefault()` 在模块顶层执行，确保 pymilvus 导入时环境变量已生效。

**改动的文件**：
- `backend/app/core/milvus_client.py` — 导入前设置 4 个 gRPC 环境变量

### 3. 手机发音按钮修复（核心）

**问题**：Android 默认浏览器（小米浏览器、三星浏览器等）点击 🔊 没声音。

**根因分析**：

1. **浏览器差异**：这些浏览器的 `window.speechSynthesis` 是空壳 API — `speak()` 接受请求但不发声，也**不触发任何事件**（`onend`、`onerror` 都不触发）
2. **代码 Bug**：`_speakLocal()` 的 5 秒超时兜底写的是 `done(true)`（返回成功），等于：浏览器假装发音成功 → 服务器兜底被跳过 → 用户听不到声音

**修复**：

| 问题 | 修复 |
|------|------|
| 超时返回 `true` 阻塞服务器兜底 | `done(true)` → **`done(false)`**，触发后端 TTS 回退 |
| 超时太长 | 5s → **2s** |
| 无 `speechSynthesis` 检查 | 新增 `if (!window.speechSynthesis) resolve(false)` 快速失败 |

**发音流程**：

```
点击 🔊 → Web Speech API 尝试 2s → 失败/无声 → POST /api/tts → Edge TTS → 播放 MP3
```

**改动的文件**：
- `frontend/src/utils/speech.ts` — 超时返回值修复 + 前置检查 + 缩短超时

### 4. 服务端 TTS 发音引擎

**问题**：最初使用 DashScope CosyVoice TTS（同 LLM 提供商），但：
1. DashScope CosyVoice 使用 **WebSocket 协议**，不是 REST，请求格式复杂
2. Google Translate TTS 在国内被墙，Docker 容器无法访问

**方案**：使用 `edge-tts`（微软 Edge 免费 TTS，无需 API Key，国内可访问）

```
POST /api/tts          → 接收 {text, voice?} → 返回 audio/mpeg
HEAD /api/tts/ping     → 探活端点
```

`edge-tts` 通过 httpx/aiohttp 调用微软 Azure TTS 服务，容器内表现稳定：
```
TTS: synthesized 10368 bytes (voice=ja-JP-NanamiNeural)
```

**改动的文件**：
- `backend/app/api/tts.py` — 新建，使用 edge-tts 合成日语语音
- `backend/app/main.py` — 注册 tts 路由
- `backend/requirements.txt` — 添加 `edge-tts>=6.0.0`

### 5. Bug 修复

| Bug | 原因 | 修复 |
|-----|------|------|
| 手机发音无声 | 超时 `done(true)` 阻塞服务器兜底 | 改为 `done(false)` + 缩短超时到 2s |
| Android 浏览器 `speechSynthesis` 空壳 | API 存在但不发声、不触发事件 | 检查 `window.speechSynthesis` 是否存在 |
| CORS 不允许局域网 IP | 白名单只有 localhost | Docker 模式自动 `allow_origins=["*"]` |
| Milvus Lite gRPC 10ms ping | pymilvus 默认值过于激进 | 环境变量设 5min |

## 技术要点

### TTS 策略

```
speakJapanese(text):
  1. Web Speech API (2s 超时)  →  成功?  → 结束
       ↓ 失败/无声
  2. POST /api/tts  (Edge TTS)  →  播放 MP3
```

三层覆蓋率：
- iOS Safari：Web Speech API 内建日语声线（零延迟）
- Android Chrome：Google 云端 TTS（`lang='ja-JP'` 时自动触发）
- 其他浏览器：服务器 Edge TTS 兜底（~1s 延迟，音质好）

### edge-tts 选型理由

| 选项 | API Key | 国内可用 | 集成复杂度 |
|------|---------|----------|-----------|
| Google TTS | ❌ 免费 | ❌ 被墙 | 低 (HTTP GET) |
| DashScope CosyVoice | ✅ 已有 | ✅ | 高 (WebSocket) |
| **Edge TTS** | **❌ 免费** | **✅** | **低 (pip install)** |
| Baidu TTS | ✅ 需申请 | ✅ | 中 (签名复杂) |

## 遗愿清单

详见 [TODOS.md](TODOS.md)。

已在 TODOS.md「已解决」区追加：
- [x] 手机浏览器发音无声（Web Speech API 超时 Bug + edge-tts 服务器兜底）
- [x] Milvus Lite gRPC too_many_pings / Invalid HTTP request
- [x] CORS 局域网 IP 访问

## 影响范围

| 模块 | 改动量 |
|------|--------|
| 后端 API | +1 文件（tts.py），大改 main.py CORS |
| 后端 Core | 修改 milvus_client.py（gRPC env vars） |
| 前端语音 | 重写 speech.ts（修复兜底逻辑） |
| 基础设施 | + Windows 防火墙 8000 入站规则 |
| 依赖 | +1 个（edge-tts） |
