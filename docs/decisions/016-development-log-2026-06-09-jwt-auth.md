# 开发日志 2026-06-09 — JWT 用户认证系统

## 概述

新增完整的 JWT 用户认证系统，替换硬编码的 `USER_ID = "default"`。后端 bcrypt 密码 + JWT 30 天过期，前端 Pinia auth store + 路由守卫。

## 改动明细

### 1. 后端认证基础设施

| 文件 | 说明 |
|------|------|
| `models/user.py` | 🆕 User 表（id, username, password_hash, created_at） |
| `core/auth.py` | 🆕 bcrypt 密码 + JWT 签发/验证 + `get_current_user` 严格模式 |
| `schemas/auth.py` | 🆕 register/login/me 的 Pydantic schema |
| `api/auth.py` | 🆕 三个端点: register, login, me |
| `core/config.py` | 🔧 加 `JWT_SECRET_KEY` 配置 |

### 2. 后端 user_id 参数化

`word_service.py` 删除 `USER_ID = "default"`，以下方法全部加 `user_id` 参数：
- `_save_words_as_mastered`, `_save_word_as_mastered`
- `toggle_favorite`, `mark_as_learned`, `mark_as_mastered`
- `get_learned_words`, `get_learned_type_counts`
- `get_mastered_words`, `get_mastered_type_counts`
- `get_favorites_paginated`, `get_word_detail`

对应的 API 路由全部注入 `get_current_user` 并传递 `str(current_user.id)`：
- `favorites.py`, `learned.py`, `mastered.py`, `words.py`

### 3. 前端认证

| 文件 | 说明 |
|------|------|
| `stores/auth.ts` | 🆕 Pinia store（token localStorage + 启动自动恢复） |
| `views/Login.vue` | 🆕 登录/注册 tabs + Stardew Valley 风格 |
| `api/index.ts` | 🔧 导出 http、Bearer token 拦截器、401 自动跳登录、SSE 加 auth header |
| `router/index.ts` | 🔧 添加 `/login` + 未登录 redirect guard |
| `App.vue` | 🔧 导航栏用户名/登出按钮 |

### 4. 全局异常处理器

`main.py` 新增三层处理器：
- HTTPException → 透传
- RequestValidationError → 422 中文提示
- Exception catch-all → 500 中文提示 + 日志堆栈

## 遗留问题

- 端口 8000 被僵尸进程 PID 7524 占用，需重启电脑释放
- edge-tts 等依赖通过手动创建 INSTALLER 文件绕过 Windows 文件锁
- 旧数据（user_id="default"）不迁移，新用户独立
