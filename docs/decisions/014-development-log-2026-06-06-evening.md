# 开发日志 2026-06-06 (晚) — 手机发音无声终极修复

## 概述

修复手机端点击发音按钮无声的问题。核心问题是 `_speakLocal` 双向误判：超时太短（400ms）导致慢速手机误触发降级，同时 `onend` 被某些浏览器假调用时却误判为成功；降级后的服务端 TTS 在移动端因 autoplay 策略也播放失败，最终无声。

## 改动明细

### 1. 修复：手机发音无声（三项修复）

| 问题 | 根因 | 修复 |
|------|------|------|
| 超时太短 | 慢速手机 400ms 内 `speaking` 未变成 true，误触发降级 | 超时延长至 **1500ms**，给足启动时间 |
| 假成功 | 部分浏览器 `onend` 立即触发但不发声 | 检测 `onend` 触发时间：< **500ms** 视为 stub |
| 降级后仍无声 | `new Audio(url).play()` 在移动端被 autoplay 策略拦截 | 改用 DOM 中复用隐藏 `<audio>` 元素 + `playsinline` |

#### 智能降级逻辑

```
speak(text)
  └─ _speakLocal(text)
       ├─ speak() → 最多等 1500ms
       │    ├─ speaking === true → 等 onend 自然结束
       │    │    └─ onend 触发时间 ≥ 500ms → ✅ 成功
       │    │    └─ onend 触发时间 < 500ms → ✅ stub，降级
       │    └─ speaking === false → ✅ stub，降级
       └─ _speakServer(text)
            └─ DOM <audio> 元素 → play() → ✅ 移动端可播放
```

### 2. 清理死代码

- 移除未使用的 `_speaking` 变量
- 移除 `speakJapanese()` 中多余的 `speechSynthesis.cancel()`（`_speakLocal()` 已做），避免 iOS Safari 双 cancel 导致静音

### 3. 部署

改动需 `docker compose build && docker compose up -d` 后生效。

## 改动的文件

| 文件 | 改动 |
|------|------|
| `frontend/src/utils/speech.ts` | 超时 400ms→1500ms、onend 时间检测、DOM audio 元素、移除死代码 |

## 影响范围

仅前端语音模块，无后端变动。
