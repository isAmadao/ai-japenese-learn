# 遗留问题 & 待办事项

## 🔴 待解决

| 优先级 | 问题 | 分类 | 说明 |
|--------|------|------|------|
| 高 | Docker 向量搜索模型下载 | 部署 | fastembed ONNX 模型在 qdrant/ 仓库使用 Xet LFS 存储，国内镜像站不支持。需国际网络或 VPN 时下载到 volume |
| 中 | 词典向量需重导入 | 数据 | ES jp_words 索引中向量由 sentence-transformers 生成，切换 fastembed 后需用同一个模型重新导入 |
| 低 | 日语分词精度 | 搜索 | 当前用 standard 分词器按字切分，可安装 analysis-kuromoji 插件提升复合词识别 |

## 🟡 待优化

| 优先级 | 优化点 | 分类 | 方案 |
|--------|--------|------|------|
| 中 | SSE 生成文章缓存 | 性能 | ✅ 流式生成后自动写 Redis，同词+同级别的同步请求直接命中缓存 |
| 中 | 收藏页按级别筛选 | 功能 | ✅ 添加 N5-N1 级别过滤 tabs + 后端 API type 参数 |
| 中 | 单词详情页关联文章空状态 | UI | ✅ `v-if="articles.length > 0"` 已正确处理 |
| 低 | 前端错误提示统一化 | UX | ✅ 封装 ErrorMessage.vue，替换 6 个视图中的分散处理 |
| 低 | 后端异常返回统一化 | 架构 | ✅ 全局 exception_handler（3 层: HTTPException → 校验错误 → Exception 兜底）+ 补齐 missing try/except |

## 🟢 待扩展

| 优先级 | 功能 | 分类 | 说明 |
|--------|------|------|------|
| 🔴 | **SRS 间隔复习系统** | 功能 | 基于"学习状态机 + 遗忘曲线"自动安排复习，参考 Anki |
| 🔴 | **测验/练习** | 功能 | 看中文选日语、听力选择、拼写填空、阅读理解 |
| 🔴 | **阅读增强** | 功能 | 文章中点击单词即时释义、一键收藏、难度标注 |
| 🔴 | **学习统计仪表盘** | 功能 | 每日学习量、复习趋势、薄弱词分析、学习时长 |
| 🟡 | **好友系统** | 功能 | 添加好友、好友学习进度对比、排行榜 |
| 🟡 | **好友聊天** | 功能 | 内置即时通讯，练习日语写作，AI 可介入纠正语法 |
| 🟡 | **文法学习** | 功能 | JLPT 文法条目（〜てしまう等），含说明和例句 |
| 🟡 | **汉字详情** | 功能 | 音读/训读、笔画顺序、构成部件 |
| 🟡 | **自定义词单** | 功能 | 按主题分类（旅行/商务/日常），创建学习列表 |
| 🟡 | **收藏文章** | 功能 | 保存 AI 生成的文章到个人文库 |
| 🟡 | **文章配图** | 功能 | ✅ Pexels 配图（手动「换一张」，随机选图） |
| 🟡 | **单词配图** | 功能 | ✅ Pexels 配图（单词详情「生成配图」按钮） |
| 🟡 | **内容类型/风格** | 功能 | ✅ 生成文章/句子可选动漫/日剧/歌曲 + 感情/搞笑等风格 |
| 🔵 | **高级 TTS** | 功能 | ElevenLabs 日语语音替代浏览器原生发音 |
| 🟡 | **智能配图** | 功能 | ✅ Chinese-CLIP 跨模态语义配图（CLIP 图库 → Pexels 二级降级） |
| 🔵 | **记忆插图** | 功能 | AI 图片生成为每个单词配记忆插图 |
| 🔵 | 浏览器插件 | 架构 | 阅读日文网页时自动取词，类似 Migaku / Yomitan |
| 🔵 | 发音评测 | 功能 | 录音 + AI 分析发音准确度 |
| 🔵 | 离线模式 | 架构 | PWA 或移动端 |
| 🔵 | 社区/语伴 | 功能 | 类似 HelloTalk 的语言交换 |

## 🔵 已解决（历史关键问题）

| 问题 | 解决方式 | 涉及文件 |
|------|----------|----------|
| 注册无邮箱验证 | 新增 email/is_verified 字段 + SMTP 验证码 | `user.py`, `auth.py`, `email_sender.py` |
| 无真人验证（机器人可批量注册） | CAPTCHA 系统（数学/Emoji/颜色随机） | `captcha.py`, `auth.py` |
| 登录无暴力破解防护 | 失败 3 次 → 真人验证（Redis 15min 窗口） | `auth.py` |
| 无法找回密码 | 邮箱验证 → 重置密码 | `auth.py` |
| JWT 30 天不刷新 | 1h access + 7d refresh token + 轮转 | `core/auth.py`, `api/auth.py` |
| 无密码强度提示 | 实时强度计算 + 进度条 | `RegisterFlow.vue`, `Settings.vue` |
| 无个人设置页 | `/settings` 页面（改昵称/密码） | `Settings.vue`, `router/index.ts` |
| 密码不能显隐切换 | 密码框添加 👁️/🙈 切换按钮 | `Login.vue`, `RegisterFlow.vue` |
| 无账号编码显示 | 注册成功 + 设置页显示 `U00001` 格式 | `RegisterFlow.vue`, `Settings.vue` |
| 邮箱不能重复注册（开发阶段） | 去掉唯一约束 + API 校验 | `user.py`, `auth.py`, `database.py` |
| 无法删除用户 | 逻辑删除字段 + 管理员删除/恢复接口 | `user.py`, `admin.py`, `AdminUsers.vue` |
| Redis 不可用时卡 4 秒 | 跳过重试 + 即时本地缓存降级 | `redis_client.py` |
| `.env` 配置未加载 | 从项目根目录（`PROJECT_ROOT`）加载 | `config.py` |
| `ModuleNotFoundError: No module named 'loguru'` | 替换为标准库 `logging` | `milvus_client.py` |
| `redis.asyncio` 不可用 | 条件导入 + 同步连接池降级 | `redis_client.py` |
| Vite `@/` 路径别名不识别 | 添加 `vite.config.ts` 的 `resolve.alias` | `vite.config.ts` |
| `article_words` 表名冲突 | 移除重复的 `ArticleWord` ORM 模型 | `models/article.py` |
| 首页单词不刷新 | 每次 `use_cache=False` 调 LLM 生成新词 | `word_service.py` |
| 朗读用中文发音 | 显式选择日语 TTS 语音 | `utils/speech.ts` |
| Milvus 安装失败 | pip 源码补丁 + 最终安装 Milvus Lite | `filesystem.py` |
| 收藏按钮无响应 | WordCard emit 只传 id，Home.vue 错当 word 对象 | `Home.vue` |
| 收藏 ID 冲突 | session id (1-5) 当 DB 主键，改为 name 去重 + 自增 id | `word_service.py` |
| 换一批/F5 混淆 | 换一批轮转 session_id，F5 读现有 ID | `api/index.ts`, `Home.vue` |
| LLM 假名读音错误 | fugashi + unidic 词典校验 | `japanese_util.py` |
| Milvus Lite fallback 标记未设置 | `_setup_fallback` 漏了 `_using_fallback = True` | `milvus_client.py` |
| 缓存词/收藏词详情 ID 冲突 | 用 Pinia store 传缓存词数据，不查 DB | `WordDetail.vue`, `stores/word.ts` |
| 换一批按钮双击 | 加载时禁用 + 显示"更换中..." | `Home.vue` |
| 手机浏览器发音无声 | Web Speech API 超时 `done(true)` 阻塞服务器兜底 → `done(false)` + edge-tts 后端 | `speech.ts`, `tts.py` |
| Milvus Lite gRPC too_many_pings | 导入前设置 4 个 gRPC 环境变量（间隔 10ms → 5min） | `milvus_client.py` |
| 局域网 CORS 拦截 | Docker 模式自动 `allow_origins=["*"]` + 防火墙规则 | `main.py` |
| 发音重叠（PC 端两次发音） | `_speakLocal` 固定 2s 超时误触服务器降级，改为智能 `speaking` 检测 | `speech.ts` |
| 手机发音无声（终极修复） | 超时 400ms→1500ms、onend <500ms stub 检测、DOM audio 适配移动 autoplay | `speech.ts` |
| 主页按钮同时出现 | 无单词时隐藏右上角按钮，仅显示欢迎区"播种新词" | `Home.vue` |
| 已学习页 🔊 被挤掉 | 发音按钮从 footer 移到 card-header 单词右侧 | `Learned.vue`, `Mastered.vue` |
| pip 文件锁补丁随升级失效 | `scripts/fix-pip-lock.py` 一键重打补丁；`scripts/fix-pip-lock.py --defender` 添加 Defender 排除 | `fix-pip-lock.py`, `fix-pip-lock.bat` |
| Qwen Embedding API 超时 | 改用 httpx 直接调用 DashScope OpenAI 兼容端点 `/v1/embeddings`，绕过 langchain 路由问题 | `base_agent.py` |
| Milvus Lite 文件锁残留 | 启动时自动删 LOCK + atexit 安全关闭 | `milvus_client.py` |
| "换一批" Token 消耗大 | Redis 词池预生成 25 词，分批取用，1 次 LLM 调用 = 5 次换一批 | `word_service.py`, `redis_client.py` |
| fugashi INSTALLER.tmp 文件锁 | `upgrade_to_mecab_stream()` 在 pip 安装失败后自动修复 INSTALLER.tmp；建议 `fix-pip-lock.py --defender` 根治 | `japanese_util.py` |
| Refresh token 队列重放错误 | 队列存储每个请求自己的 config，刷新后用各自 config 重放 | `api/index.ts` |
| `check-email` 永远返回 true | 改为真实数据库查询 | `auth.py` |
| 文章接口无鉴权 | 三个文章端点加上 `get_current_user` 依赖 | `articles.py` |
| 分页无加载态 | 增加 loading-overlay 旋转动画 | `Favorites.vue`, `Learned.vue`, `Mastered.vue` |
| 旧注册接口无防护 | 删除无邮箱验证的 `POST /api/auth/register` | `auth.py` |
| TTS blob URL 泄漏 | 设置新 URL 前先 revoke 上一个 | `speech.ts` |
| SSE 不走 axios auth | `_ensureAuthToken()` 预刷新 token + 401 自动重试 | `api/index.ts` |
| 找回密码暴露邮箱 | 无论邮箱是否存在都返回成功 | `auth.py` |
| 管理端 N+1 查询 | 改为两次批量 GROUP BY | `admin.py` |
| 词典升级 SSE 无重试 | 增加 2 次重试 + token 预刷新 | `api/index.ts` |
| Learned/Mastered 没例句 | 卡片中显示第一条例句 | `Learned.vue`, `Mastered.vue` |
| 忘记密码计时器未清理 | `onUnmounted` 清理 `forgotCooldownTimer` | `Login.vue` |
| 朗读全文按钮溢出 | 改为 `width: auto` 自适应 | `ArticleDetail.vue` |

## 标签索引

```
#环境问题  #功能缺失  #性能优化  #UI优化  #架构扩展  #安全增强  #已解决
```


