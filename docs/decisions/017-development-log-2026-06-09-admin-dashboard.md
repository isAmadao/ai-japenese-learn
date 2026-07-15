# 开发日志 2026-06-09 — Admin 角色权限 + 管理后台

## 概述

新增 `role` 字段实现权限分级（user/admin），创建 admin/admin 默认管理员账号，实现完整的管理后台页面（侧边栏布局 + 统计概览 + 用户/单词/文章管理）。

## 改动明细

### 1. 权限分级 (role-based access)

| 文件 | 说明 |
|------|------|
| `models/user.py` | 🔧 新增 `role` 字段（String(20)，默认 `"user"`，可选 `"admin"`） |
| `schemas/auth.py` | 🔧 TokenResponse / UserResponse 加 role |
| `core/auth.py` | 🔧 用 `bcrypt` 替代 `passlib`（修复 bcrypt 5.x 兼容性）、新增 `require_admin` FastAPI 依赖 |
| `api/auth.py` | 🔧 注册/登录返回 role、禁止注册 admin 用户名、启动时 seed admin/admin |
| `core/database.py` | 🔧 `_ensure_columns()` 通过 ALTER TABLE 兼容旧表、启动时调用 `seed_admin()` |
| `requirements.txt` | 🔧 清理 passlib，直接依赖 bcrypt |

### 2. 后端管理 API (`api/admin.py` 🆕)

所有接口由 `require_admin` 依赖保护：

| 接口 | 功能 |
|------|------|
| `GET /api/admin/stats` | 总用户数/单词数/收藏数/文章数 + JLPT 级别分布 |
| `GET /api/admin/users` | 分页用户列表（含收藏数/已学数） |
| `GET /api/admin/words` | 分页单词列表（含收藏次数），支持 JLPT 级别筛选 |
| `GET /api/admin/articles` | 分页文章列表 |

### 3. 前端管理页面

| 文件 | 说明 |
|------|------|
| `views/admin/AdminLayout.vue` | 🆕 左侧木纹侧边栏 + 顶栏 + RouterView 内容区 |
| `views/admin/AdminDashboard.vue` | 🆕 4 个统计卡片 + JLPT 级别分布条形图 |
| `views/admin/AdminUsers.vue` | 🆕 用户表格（角色徽标 + 收藏/已学统计 + 分页） |
| `views/admin/AdminWords.vue` | 🆕 单词表格（JLPT 级别筛选 + 分页） |
| `views/admin/AdminArticles.vue` | 🆕 文章表格（ID/标题/级别/单词数 + 分页） |
| `router/index.ts` | 🔧 添加 `/admin` 嵌套路由（Dashboard/Users/Words/Articles）+ admin role 守卫 |
| `App.vue` | 🔧 admin 用户导航栏显示金色「⚙️ 管理」链接 |
| `stores/auth.ts` | 🔧 AuthUser 加 role、暴露 isAdmin getter、登录/注册保存 role |
| `api/index.ts` | 🔧 新增 fetchAdminStats/fetchAdminUsers/fetchAdminWords/fetchAdminArticles |

### 4. bcrypt 兼容性修复

passlib 1.7.4 与 bcrypt 5.x 不兼容，用直接 bcrypt 调用替代 passlib.CryptContext，消除了启动时的 bcrypt version warning。

## 验证

- admin/admin 登录 → `role: "admin"` ✅
- 普通用户注册 → `role: "user"` ✅
- 禁止注册 admin 用户名 ✅
- `/api/admin/stats` 返回完整统计数据 ✅
- `/api/admin/users` 分页用户列表 ✅
- `/api/admin/words` 按 JLPT 级别筛选 ✅
- 非 admin 用户调 admin 接口 → 403 「需要管理员权限」✅
- 前端 TypeScript 类型检查 + 生产构建通过 ✅

## 遗留问题

- 已有用户 localStorage 不包含 role 字段，需重新登录后才能看到管理入口（一次性迁移问题）
- 管理页面暂无删除/编辑操作（只读管理，后续可按需扩展）
