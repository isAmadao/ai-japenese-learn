# 📊 开发日志 · 决策与优化全景

本文件聚合了所有 ADR 的核心信息，便于快速回顾和 AI 学习。

## 架构全景


2026-07-06  图片搜索单词 + 结果持久化 + 环境镜像修复
├── 📸 feat: 图片搜索单词（上传→OCR+LLM Vision→搜词→CLIP 图库）
├── 🔧 fix: EasyOCR 语言参数 ["ja", "en"]（去掉 ch_sim）
├── 🔧 fix: LLM Vision 多模型降级（qwen-vl-max → qwen-vl-plus）
├── 📦 feat: 前端 sessionStorage + URL 双重重试持久化
├── 🎨 feat: 新增 restored 标志解决 blob URL 不可跨页问题
├── 🔧 fix: CLIP 图库去重（字节哈希 → 向量相似度 > 0.99）
├── 🔧 fix: query watcher 覆盖 URL img 参数问题
├── 🔧 fix: 模板 previewUrl 条件隐藏 OCR 结果区
├── 🐳 chore: HF_ENDPOINT 镜像配置（hf-mirror.com）
├── 🔧 fix: Milvus Lite 残留目录导致创建集合失败
└── 📝 doc: 022 开发日志
2026-07-05  CLIP 跨模态智能配图系统
├── 🧠 feat: Chinese-CLIP 文图编码服务（FP16, 512d, 懒加载）
├── 📦 feat: Milvus clip_image_vectors 集合（+search/store/smart_match）
├── 🔌 feat: 智能配图 API（CLIP → Pexels 二级降级，图库自动积累）
├── 🎨 feat: 前端「🧠 智能配图」按钮（紫色像素风，与现有「🔄 换一张」并排）
├── 🧪 test: CLIP 编码 + Milvus KNN + 语义区分 端到端验证
└── 📝 doc: 021 开发日志
├── 🏗️ feat: 认证系统独立为 auth-kit 包（配置注入 + 依赖注入 + 无耦合）
├── 🏗️ feat: auth-client 客户端包（~50行，仅依赖 fastapi + jose）
├── 🏗️ feat: auth-service 独立认证微服务
├── 🎵 fix: 离开页面停止 TTS（stopSpeech() + onUnmounted 全页面覆盖）
├── 🔍 feat: ES 单词搜索（BM25 倒排索引 + 向量 KNN 两路召回）
├── 📚 feat: 14,307 词导入 ES（jp_words 索引，384 维向量）
├── 🏠 feat: 本地语义模型（sentence-transformers / fastembed 双后备）
├── 🔍 feat: 前端搜索页面（防抖输入 + 结果卡片 + 朗读）
├── 🐳 chore: Docker 镜像重建（267MB，BM25 搜索，带 fastembed）
├── 🧪 test: 多模态智能体项目验证 auth-kit 集成
└── 📝 doc: 020 开发日志
├── 🔐 feat: JWT 用户认证系统（register/login/me + bcrypt 密码）
├── 🔐 feat: User 表 role 字段（user/admin）+ admin 账号 seed
├── 🔧 fix: passlib → 直接 bcrypt（修复 bcrypt 5.x 兼容性）
├── 🔧 feat: require_admin FastAPI 依赖装饰器
├── 📊 feat: 4 个 admin-only API（stats/users/words/articles）
├── 🎨 feat: 管理后台前端（侧边栏 + 统计卡片 + 数据表格）
├── 🛡️ feat: 路由守卫 admin role 检查 + 金色管理入口
└── 📝 doc: 新增 016/017 开发日志 + 更新 SUMMARY

2026-06-14  (Session 2) API Key 提取 + 内容风格 + Pexels 配图 + 批量修 Bug + Docker
├── 🔑 feat: LLM API Key 提取到前端（首页填写，localStorage 存储）
├── 🎨 feat: 内容类型（动漫/日剧/歌曲）和风格（感情/搞笑/冒险等）选择
├── 📸 feat: Pexels 配图系统（手动「生成配图」/「换一张」按钮）
├── 🐛 fix: 批量修复 15 个遗留 Bug（token 队列/鉴权/分页/N+1/泄漏等）
├── 🐳 feat: Docker 打包部署（nginx + app + redis 三容器）
├── 🗺️ doc: MCP 集成方向记录（019）+ 开发日志（020）
└── 🔧 chore: README 上线提醒 + 日志系统更新

2026-06-14  MCP 工具集成 — Pexels 配图 + Brave Search 真实例句
├── 📸 feat: Pexels 自动配图（文章生成后搜图 + Article.image_url + 前端展示）
├── 🌐 feat: Bing Search 真实例句搜索（日文网页句段提取 + 来源展示）
├── 📝 doc: 新增 019 决策记录 + 更新 TODOS
└── 🗺️ 记录后续 MCP 方向（ElevenLabs / 记忆图 / YouTube 等）

2026-06-07  批量修复遗留问题（pip锁/Embedding/Milvus锁/词池/fugashi）
├── 🔧 feat: pip 文件锁一键修复脚本 `scripts/fix-pip-lock.py`
├── 🔧 feat: Qwen Embedding 改用 httpx 直连 DashScope（真实语义向量）
├── 🔧 feat: Milvus Lite 启动自动删 LOCK + atexit 安全关闭
├── 🚀 perf: Redis 词池预生成（1 次 LLM = 5 次换一批，零延迟）
├── 🔧 feat: fugashi INSTALLER.tmp 自动修复
├── 🐛 fix: ShellExecuteExW 提权（解决 MINGW64 下 UAC 弹窗问题）
└── 📝 doc: 新增 015 开发日志 + 更新 TODOS 全景
```

2026-06-06  局域网部署 + 手机发音修复 + gRPC 优化
├── 🌐 feat: 局域网部署（CORS 通配 + 防火墙规则）
├── 🔊 feat: 服务端 TTS 兜底（edge-tts，免费无需 Key）
├── 🐛 fix: 手机浏览器发音无声（超时 done(true) 阻塞服务器兜底）
├── 🐛 fix: Milvus Lite gRPC too_many_pings（4 个环境变量）
├── 🐛 fix: CORS 不允许局域网 IP（Docker 模式自动通配）
├── 🎯 refactor: TTS 三层策略（WebSpeech → Edge TTS 服务器）
└── 📝 doc: 更新开发日志
```
┌──────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Vite + TypeScript)                    │
│  ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐   │
│  │  Home   │ │Favorites │ │ WordDetail │ │Article   │   │
│  │ (随机5词)│ │(6列收藏) │ │ (详情/朗读) │ │ (文章)   │   │
│  └────┬────┘ └────┬─────┘ └─────┬──────┘ └────┬─────┘   │
│       └───────────┴─────────────┴──────────────┘          │
│                       │ Axios / SSE fetch                  │
└───────────────────────┼──────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────┐
│  Backend (FastAPI + uvicorn)                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ API 路由 │─>│ Service  │─>│  Agent (BaseAgent)    │   │
│  │ (路由+   │  │ (业务编排)│  │  ├─ ChatOpenAI (Qwen) │   │
│  │  校验)   │  │          │  │  ├─ Redis 缓存        │   │
│  └──────────┘  └──────────┘  │  ├─ Embedding (hash)  │   │
│                              │  └─ Milvus 存储       │   │
│                              └──────────────────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ SQLite   │  │  Redis   │  │  Milvus Lite         │   │
│  │ (单词/   │  │ (LLM缓存)│  │  (向量存储)           │   │
│  │  收藏)   │  │          │  │                      │   │
│  └──────────┘  └──────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────┘

2026-06-06  局域网部署 + 手机发音修复 + gRPC 优化
├── 🌐 feat: 局域网部署（CORS 通配 + 防火墙规则）
├── 🔊 feat: 服务端 TTS 兜底（edge-tts，免费无需 Key）
├── 🐛 fix: 手机浏览器发音无声（超时 done(true) 阻塞服务器兜底）
├── 🐛 fix: Milvus Lite gRPC too_many_pings（4 个环境变量）
├── 🐛 fix: CORS 不允许局域网 IP（Docker 模式自动通配）
├── 🎯 refactor: TTS 三层策略（WebSpeech → Edge TTS 服务器）
└── 📝 doc: 更新开发日志
```

## 关键技术决策速览

| 决策 | 选型 | 核心理由 | 备选 |
|------|------|----------|------|
| 关系型 DB | SQLite / MySQL | 开发零配置 / 生产稳定 | PostgreSQL |
| 向量 DB | Milvus Lite | 嵌入式，免服务 | ChromaDB（太重） |
| Web 框架 | FastAPI | 自动文档，类型安全 | Flask, Django |
| LLM | Qwen (DashScope) | 低价，中日文强，免代理 | GPT-4o, Claude |
| LLM 框架 | LangChain | 标准化 Prompt/模型切换 | 直接调用 API |
| 缓存 | Redis | 高性能，TTL 灵活 | 内存缓存 |
| 前端 | Vue 3 + TS | 轻量，响应式 | React, Svelte |
| CAPTCHA | Turnstile (待实施) | 免费无感，隐私友好 | reCAPTCHA, 极验 |
| 注册验证 | SMTP 邮箱 (待实施) | 零成本，替代短信 | 阿里云短信, Twilio |

## 关键优化点（按价值排序）

### 🥇 Agent + Redis 缓存系统
- **问题**: 每次调 LLM 等 5-10s，Token 消耗大
- **方案**: Agent 封装 LLM + Redis 缓存 + 降级
- **效果**: 缓存命中 → 100ms，Token 费用降低 90%+
- **学习点**: 降级策略比完美实现更重要

### 🥇 SSE 流式输出
- **问题**: 用户无所事事等 5-10s 看结果
- **方案**: StreamingResponse + 逐 token SSE + 后台线程向量存储
- **效果**: 首字 2s 出现，生成完即展示，向量后台存
- **学习点**: 感知性能 > 实际性能

### 🥇 Milvus Lite 迁移
- **问题**: Milvus 标准版需独立服务，部署复杂
- **方案**: pymilvus `MilvusClient` 本地文件模式
- **效果**: 单文件向量库，零配置
- **学习点**: 三层降级（Lite → numpy → 报错提示）

### 🥈 确定性哈希向量
- **问题**: Embedding API 不可用时向量存储完全失效
- **方案**: SHA256 生成可复现单位向量
- **效果**: Embedding 始终可用
- **学习点**: 可用性 > 精度

### 🥈 Redis 同步/异步双模式
- **问题**: 同步 Agent 代码无法调用 async Redis
- **方案**: RedisClient 同时维护 sync + async 连接
- **效果**: 双模式共存无需重构

### 🥈 pip 文件锁补丁
- **问题**: Windows + conda 下 pip 无法安装任何包
- **方案**: 修改 pip 源码的 `os.unlink` → try/except
- **效果**: milvus-lite 装上了
- **学习点**: 区分"权限问题"和"文件锁问题"

### 🥇 数据流 v2 — 仅收藏单词持久化
- **问题**: 所有 LLM 生成单词都写入 DB，DB 膨胀且 session id 与 DB 主键冲突
- **方案**: 生成结果存 Redis (session 隔离)，仅收藏时写入 DB
- **效果**: DB 只存用户真正需要的单词，session 刷新不丢缓存
- **学习点**: 缓存/持久化分离，按数据价值分层存储

### 🥈 Session ID 轮转 — 区分"换一批"和 F5
- **问题**: "换一批"和 F5 都调同一接口，后端无法区分
- **方案**: "换一批"生成新 session_id 写入 localStorage → Redis 找不到旧缓存 → LLM 生成；F5 读现有 session_id → Redis 命中
- **效果**: "换一批"出新词，F5 保持当前词
- **学习点**: 前端状态驱动后端缓存策略

### 🥈 MeCab 假名校验 → pykakasi 轻量替换
- **问题**: mecab-ipadic-utf8 词典 523MB 导致 Docker 镜像臃肿
- **方案**: 默认 pykakasi（~10MB），可选在线升级至 fugashi + unidic-lite（~50MB）
- **效果**: 镜像从 1.33GB 降至 712MB（-600MB），N5-N1 读音校验准确率不变
- **学习点**: 轻量默认 + 可选升级 = 兼顾体积和精度

### 🥉 学习状态机 — favorite → learned → mastered
- **问题**: 无法区分"已收藏"、"已学习"和"已熟练"三个阶段
- **方案**: Favorite 表 status 字段扩展为 mastered|favorite|learned
- **效果**: LLM 生成词自动持久化（mastered），取消收藏也回退至 mastered
- **学习点**: 状态机加字段比新建表更简单

### 🥉 收藏状态 V-model 共享
- **问题**: 首页收藏后进详情页显示未收藏，详情页取消收藏首页星标不同步
- **方案**: favoritedIds 从 Home 局部变量提至 Pinia store
- **效果**: 首页/详情页收藏状态实时同步

### 🥈 手机 TTS 三层降级策略
- **问题**: Android 默认浏览器（小米/三星等）`speechSynthesis` 是空壳 API，`speak()` 接受请求但不发声也不触发任何事件
- **方案**: Web Speech API → 2s 超时 `done(false)` → 服务器 Edge TTS 兜底
- **效果**: 手机端发音覆盖率从 ~60%（仅 Chrome/iOS）提升至 ~99%（所有浏览器）
- **学习点**: 浏览器 API 超时兜底要用 `done(false)` 而非 `done(true)`，否则服务器降级被阻塞

### 🥈 Milvus Lite gRPC 配置
- **问题**: pymilvus 默认 gRPC keepalive 间隔 10ms，导致 `too_many_pings` + uvicorn `Invalid HTTP request` 日志污染
- **方案**: 导入前设 `GRPC_ARG_KEEPALIVE_TIME_MS=300000` 等 4 个环境变量
- **效果**: 日志干净，连接稳定
- **学习点**: 嵌入式数据库的 gRPC 参数需要显式配置，不能依赖默认值

## 技术债务

### 环境相关
- [ ] pip 补丁在升级后会失效（#环境问题）
- [ ] Windows Defender 排除 conda 目录可根治
- [ ] fugashi 的 INSTALLER.tmp 重命名仍会被锁（#环境问题）

### 功能缺失
- [ ] Qwen Embedding API endpoint 待确认（#功能缺失）
- [ ] 用户认证系统（#架构扩展）
- [ ] 单词 SRS 间隔重复（#功能缺失）

### 性能
- [ ] 换一批每次调 LLM，Token 消耗大（#性能优化）
- [ ] 预生成单词池（#性能优化）
- [ ] pykakasi → MeCab 升级在 Docker 中需网络连通（需预装或代理）

### 已解决
- [x] 收藏按钮无响应（WordCard emit 类型不匹配）
- [x] Session id 与 DB 主键冲突
- [x] LLM 假名读音错误（pykakasi/MeCab 双引擎）
- [x] DB ext 字段被误用（已清除，留给生产环境）
- [x] 取消收藏的词不进入已熟练列表（改为 status=mastered）
- [x] Docker 容器化部署（多阶段构建 + docker-compose）
- [x] Redis 不可用时缓存功能失效（本地内存缓存降级）
- [x] 首页首次加载无控制即调 LLM（改为欢迎界面）
- [x] SSE 行级流式输出（单词逐行展示）

## 文件时间线


2026-06-06  局域网部署 + 手机发音修复 + gRPC 优化
├── 🌐 feat: 局域网部署（CORS 通配 + 防火墙规则）
├── 🔊 feat: 服务端 TTS 兜底（edge-tts，免费无需 Key）
├── 🐛 fix: 手机浏览器发音无声（超时 done(true) 阻塞服务器兜底）
├── 🐛 fix: Milvus Lite gRPC too_many_pings（4 个环境变量）
├── 🐛 fix: CORS 不允许局域网 IP（Docker 模式自动通配）
├── 🎯 refactor: TTS 三层策略（WebSpeech → Edge TTS 服务器）
└── 📝 doc: 更新开发日志

2026-06-06 (下)  星露谷 UI + 技能系统 + 发音重叠修复
├── 🎨 feat: 星露谷物语像素 UI（木质 UI + 天空渐变 + Press Start 2P）
├── 🤖 feat: Claude Code 技能系统（CLAUDE.md + skill-creator/find-skills/frontend-design）
├── 🔧 feat: OpenSpec OPSX 工作流（propose/apply/archive）
├── 🐛 fix: 发音重叠（_speakLocal 固定 2s 超时误触服务器降级）
├── 🐛 fix: 主页"播种"/"换一批"按钮同时出现
├── 🐛 fix: 已学习页 🔊 被"已熟练"按钮挤掉
├── 🎯 refactor: 前端全局字号放大 + 对比度提升
└── 📝 doc: 更新开发日志

2026-06-06 (晚)  手机发音无声终极修复
├── 🐛 fix: 手机发音无声（超时 400ms→1500ms + onend <500ms 检测 stub）
├── 🐛 fix: 降级后 TTS 仍无声（new Audio → DOM hidden <audio> 适配移动 autoplay）
├── 🎯 refactor: 移除无用 _speaking 变量 + 双 cancel（iOS 静音风险）
└── 📝 doc: 更新开发日志
```

2026-06-14  Nginx 代理 + 字典预载 + 句子换新 + 相似度去重
├── 🌐 feat: Nginx 反向代理（SSL 骨架 + SSE 支持 + 动态 DNS 解析）
├── 📚 feat: 14,307 词 JLPT 预载词典（零 LLM 成本，瞬间换一批）
├── 🆕 feat: "句子换新" AI 例句重写 + 追加保留旧句
├── 🔧 feat: 通用文本相似度去重 via Milvus-Lite + DashScope Embedding
├── 🔧 fix: JSON 解析容错（自动修复 LLM 少逗号/尾逗号）
├── 🐛 fix: 词池词量不够（旧 LLM 去重后 <5 个）
├── 🐛 fix: Starlette ProxyHeadersMiddleware 不存在
├── 🐛 fix: Docker volume 覆盖字典文件
├── 📝 doc: 018 开发日志 + 架构分析
└── 🔮 plan: 后续方向（SRS/测验/阅读增强/统计）

2026-06-14 (下)  安全升级：注册验证 + 登录防护 + 个人设置
├── 🔐 feat: 邮箱验证注册（昵称/邮箱/密码 → CAPTCHA → 验证码 → 注册成功）
├── 🔐 feat: 三种 CAPTCHA 随机切换（数学/Emoji/颜色）
├── 🔐 feat: 登录失败 3 次→真人验证（Redis 计数器 + 15min 窗口）
├── 🔐 feat: 忘记密码（邮箱验证 → 重置密码）
├── 🔐 feat: JWT 刷新机制（1h access + 7d refresh + token 旋转）
├── 🔐 feat: SMTP 邮件发送 + 开发模式自动降级
├── 🔐 feat: 密码强度提示（注册/修改密码实时显示）
├── 🔐 feat: 记住登录状态（localStorage / sessionStorage 切换）
├── 🔐 feat: 登录后跳转回原页面（`?redirect=` 参数）
├── ⚙️ feat: 个人设置页 `/settings`（修改昵称/密码）
├── 🐛 fix: Redis 不可用时 4s 超时（即时降级到本地缓存）
├── 🐛 fix: `.env` 未从项目根目录加载
├── 👁️ feat: 密码显隐切换按钮（登录/注册/设置）
├── 🆔 feat: 账号编码 `U00001` 格式显示（注册成功 + 设置页）
├── 🔄 feat: 邮箱开发模式可重复注册
├── 🔐 feat: 管理后台逻辑删除/恢复用户
├── 📝 doc: 011 安全升级 ADR + 更新日志
└── 🐳 chore: 重构 Docker 镜像

2026-06-07  批量修复遗留问题（5 个高/中优先级）
├── 🔧 feat: pip 文件锁一键修复脚本 `scripts/fix-pip-lock.py`
├── 🔧 feat: Qwen Embedding 改用 httpx 直连 DashScope（真实语义向量）
├── 🔧 feat: Milvus Lite 启动自动删 LOCK + atexit 安全关闭
├── 🚀 perf: Redis 词池预生成（1 次 LLM = 5 次换一批，零延迟）
├── 🔧 feat: fugashi INSTALLER.tmp 自动修复
├── 🐛 fix: ShellExecuteExW 提权（解决 MINGW64 下 UAC 弹窗问题）
└── 📝 doc: 新增 015 开发日志 + 更新 TODOS 全景

2026-06-04
├── 18:00  🎉 项目初始化 (commit 1)
├── 18:15  🐛 fix: 模型表冲突 + requirements
├── 19:00  🐛 fix: redis.asyncio + SSE 流式
├── 19:30  🐛 fix: replace loguru with logging
├── 20:00  🤖 feat: Agent 系统 + 缓存 + 向量
├── 20:30  🔧 refactor: Milvus → numpy 向量存储
├── 21:00  🔧 refactor: pip 补丁 → Milvus Lite
├── 21:30  🐛 fix: 换一批不刷新问题
├── 21:45  🐛 fix: 日语 TTS 语音选择
├── 22:00  📝 feat: install-japanese-tts 技能
├── 22:30  📝 doc: 开发日志系统
├── 23:00  🔧 refactor: 数据流 v2（仅收藏持久化）
├── 23:15  🐛 fix: 收藏按钮无响应（emit 类型不匹配）
├── 23:20  🐛 fix: 收藏 ID 冲突（name 去重）
├── 23:25  🐛 fix: 换一批 vs F5 区分（session_id 轮转）
├── 23:35  🔊 feat: install-japanese-tts 技能生效验证
├── 23:40  🐛 fix: Milvus Lite fallback 标记未设置
├── 23:45  🤖 feat: MeCab 假名校验（fugashi + unidic）
├── 23:55  📝 doc: 更新开发日志
└── 00:15  📝 feat: 学习状态机（favorite → learned）+ 已学习页面
          🐛 fix: 缓存词/收藏词详情 ID 冲突（Pinia store）
          🐛 fix: 换一批按钮加载禁用 + "更换中..."

2026-06-05  大规模功能完善 + 容器化
├── 🔧 refactor: 状态机扩展 mastered→favorite→learned→mastered
├── 🎯 feat: 新增「已熟练」页面 + API
├── 📡 feat: SSE 行级流式输出（单词逐行展示）
├── 🔄 feat: 分层重试机制（前端axios + 后端LLM）
├── 🐳 feat: Docker 多阶段构建 + docker-compose 编排
├── 💾 feat: Redis 本地内存缓存降级
├── 📘 feat: pykakasi 替换 MeCab + 在线升级/回退按钮
├── 🎨 feat: 首页欢迎界面 + 动态按钮文字
├── 🐛 fix: 收藏状态跨页不同步（Pinia store 共享）
├── 🐛 fix: 详情页取消收藏不生效（始终传 ext）
├── 🐛 fix: DB ext 字段被误用（移除赋值）
├── 🐛 fix: settings 模块名冲突（重命名 dictionary）
├── 🐛 fix: MeCab 回退不持久（.dict_preference 标记）
├── 🐛 fix: SSE 生成器向量存储不执行（后台线程 + 提前启动）
├── 🐛 fix: Milvus Lite 集合未 load（查询报 released）
├── 🐛 fix: Milvus insert 未动态降级（异常时切 numpy）
├── 🧪 test: 46个测试用例（状态机/API/并发/性能）
└── 📝 doc: 更新开发日志

2026-06-06  局域网部署 + 手机发音修复 + gRPC 优化
├── 🌐 feat: 局域网部署（CORS 通配 + 防火墙规则）
├── 🔊 feat: 服务端 TTS 兜底（edge-tts，免费无需 Key）
├── 🐛 fix: 手机浏览器发音无声（超时 done(true) 阻塞服务器兜底）
├── 🐛 fix: Milvus Lite gRPC too_many_pings（4 个环境变量）
├── 🐛 fix: CORS 不允许局域网 IP（Docker 模式自动通配）
├── 🎯 refactor: TTS 三层策略（WebSpeech → Edge TTS 服务器）
└── 📝 doc: 更新开发日志
```
