# 阶段3：Agent 系统重构 — ReAct 多步推理 + 工具系统

> 从 one-shot LLM 封装升级为真正的 Agent 系统（工具注册 + 多步流水线）
> 状态：🚧 进行中

---

### 2026-07-13：基础架构重构 + ReAct 工具系统 + 死代码清理

#### 完成内容

**1. 代码架构重组（提取关注点）**

- **`base_agent.py`** 瘦身：439行 → 155行
  - `_extract_json()` → 提取为 `utils/json_utils.py`（纯函数）
  - `_embed_via_api()`、`warm_local_model()`、`_embed_local()`、`_make_deterministic_vector()`、`_embed_and_store()` → 提取为 `services/vector_service.py`
  - `dedup_by_text()` → 移到 `services/word_service.py`（唯一调用方）
- **`article_agent.py`** 清理：删 `_prepare_article_prompt()`、更新 docstring
- **`word_agent.py`** 清理：删 `_verify_single_kana()`（改用工具调用）

**2. 工具系统基础设施**

- 新建 `agent/tool.py` — `AgentTool` 数据类 + `make_tool()` 辅助函数
  - 工具定义：name、description、fn、parameters（JSON Schema）
  - 自动从函数签名推断参数类型和必填项
  - `format_for_prompt()` → 工具描述文本块，注入 LLM system prompt
- `BaseAgent` 新增：`tools` 类变量 + `tool_specs_for_prompt()` + `run_tool()`

**3. ArticleAgent ReAct 流程（生成前校验 → 规划 → 生成 → 自检）**

- `verify_kana` 工具 — 生成前校验每个单词的读音（MeCab/pykakasi）
- `_plan_article()` — 独立的 LLM 规划步骤（带缓存），输出标题 + 段落结构 + 词分布
- 覆盖度检查：
  - 规划后：检查所有单词是否分配到段落，遗漏则自动补充
  - 生成后：检查文章中实际出现的单词，缺失则 log 警告
- `_make_article_prompt(plan=...)` — 规划作为上下文注入主生成 prompt

**4. WordAgent 工具集成**

- `verify_kana` 工具 — 生成后校验读音
- `lookup_dictionary` 工具 — 从 `jlpt_words.json`（14k 词条）查词
- `_cross_check_dict()` — 生成后交叉校验，如果存在于标准词库，用词库的规范数据覆盖 LLM 输出
- `generate_words()` / `generate_words_stream()` 均集成了 kana 校验 + 词典校验

**5. 死代码清理**

| 文件 | 原因 |
|------|------|
| `services/llm_service.py` | 被 agent 系统取代，无人引用 |
| `services/article_service.py` | 仅包装 `generate_article()`（已删），`get_article` 内联到 API |
| `agent/article_agent.py` 中的 `generate_article()` | 阻塞版，前端只用流式版 |
| `schemas/auth.py` | 旧自管用户系统残留，auth-service 接管 |
| `core/captcha.py` | 同上 |
| `core/email_sender.py` | 同上，且 SMTP 配置已从 config.py 移除 |
| `core/retry.py` | 重试装饰器工具，无人引用 |
| `services/fix_prompt.py` | 一次性修复脚本，任务已完成 |

**6. 新建/整合的工具模块**

| 文件 | 用途 |
|------|------|
| `utils/json_utils.py` | JSON 提取纯函数（从 base_agent 提取） |
| `utils/prompt_utils.py` | style instruction 构建（从 article_agent 提取） |
| `services/vector_service.py` | embedding + Milvus 存储（从 base_agent 提取） |
| `agent/tool.py` | AgentTool 数据类 + make_tool（新建） |

#### 问题 & 解决方案

**问题1：`conda run` 在 Windows 上不支持多行 `-c` 参数**

现象：`conda run -n env python -c "..."` 在 Windows 上报错 `NotImplementedError`
根因：conda 的 `wrap_subprocess_call` 对 Windows 上含换行的 `-c` 脚本未实现
解决：将测试脚本写入临时文件后执行 `conda run -n env python file.py`；生产代码验证改用 `py_compile.compile()`
效果：语法验证无需 conda 环境

**问题2：SSL_CERT_FILE 导致 base (非 conda) 环境 ChatOpenAI 初始化失败**

现象：`from app.agent.article_agent import article_agent` 报 `FileNotFoundError: ssl.py`
根因：Python 全局环境 `SSL_CERT_FILE` 指向不存在的 `D:\miniconda3/ssl/cacert.pem`
解决：在 conda 环境 `ai-japanese-learn` 中验证，该环境 cert 配置正确
效果：conda 环境下 agent 加载正常

#### 待办/下一步

- [ ] Step B：StudentAgent — 个性化学习 Agent（跟踪用户进度、推荐复习、出题）
- [ ] 文章生成后缺失单词的自动补充（目前仅 log 警告）
- [ ] `lookup_dictionary` 工具可扩展到 fuzzy match（当前精确匹配）

---

### 2026-07-14：场景标签系统 + 代码结构优化

#### 完成内容

**1. 词库场景标签系统（零 LLM 成本）**

- Word 模型新增 `scene` JSON 字段，支持多标签（如 `["日常生活","旅游"]`）
- 数据库启动自动迁移，兼容旧表
- LLM + 关键词混合打标脚本 `scripts/tag_scenes.py`
  - 关键词预匹配（工作/商务/旅游/动漫/影视剧）
  - LLM 批处理剩余单词（200 词/批，约 66 批完成）
  - 全部 14,307 个 JLPT 词汇完成打标
- 场景分布：日常 80% | 影视 7% | 工作 6% | 动漫 4% | 商务 4% | 旅游 3%

**2. 场景过滤 API + 前端**

- `api/words.py` — `/random` 和 `/random/stream` 加 `scene` 查询参数
- `word_service.py` — `_pick_random_dict_words()` 支持按场景过滤，Redis 缓存 key 包含 scene
- `schemas/word.py` + `types/index.ts` — CachedWord/WordResponse 加 `scene` 字段
- `Home.vue` — 场景选择芯片栏 🌐全部/🏠日常/💼工作/🏢商务/🎬影视/🎮动漫/✈️旅游
- `WordCard.vue` — 卡片显示场景标签
- `stores/word.ts` + `api/index.ts` — 场景状态管理 + 请求参数传递

**3. 代码结构优化（三批次）**

**第一批：Bug 修复 + 死代码清理**
| 改动 | 文件 | 说明 |
|------|------|------|
| 加 `get()` 方法 | `core/milvus_client.py` | `image_search.py` 调了不存在的方法 |
| 删 `getBingKey` | `views/Home.vue` | 不存在函数的引用 |
| 删死代码 | `views/ImageSearch.vue` | 741 行无路由页面，功能已在 Search.vue |
| 删未用 API | `api/index.ts` | `loginUser`/`registerUser`/`fetchMe`/`checkEmailAvailable` |

**第二批：减少重复**
| 改动 | 文件 | 说明 |
|------|------|------|
| 新建 | `utils/constants.ts` | 集中管理 localStorage key、TYPE_TABS、SCENES、PAGE_SIZE |
| 新建 | `utils/shared.ts` | `typeColor()`、`sleep()` 共享函数 |
| 引用 | `views/Search.vue` | 改用共享 `typeColor`、`STORAGE_KEYS` |
| 引用 | `views/Favorites.vue` | 改用 `TYPE_TABS` |
| 清理 | `requirements.txt` | 移除 `pydantic-settings`、`python-jose` |

**第三批：架构优化（部分）**
| 改动 | 文件 | 说明 |
|------|------|------|
| 改名 | `api/dictionary.py` → `api/settings.py` | 文件名与路由前缀一致 |
| 更新引用 | `main.py` | 同步 import |

#### 待办/下一步
- [ ] Step B：StudentAgent — 个性化学习 Agent（跟踪用户进度、推荐复习、出题）
- [ ] 文章生成后缺失单词的自动补充（目前仅 log 警告）
- [ ] `lookup_dictionary` 工具可扩展到 fuzzy match（当前精确匹配）

#### 问题 & 解决方案

**问题1：Conda 环境缺失 sentence-transformers**

现象：`INFO:app.services.vector_service:No local embedding model available`
根因：用户使用 Conda 环境 `ai-japanese-learn`，但该环境未安装 `sentence-transformers`
解决：`conda activate ai-japanese-learn` → `pip install sentence-transformers`，并通过 `hf-mirror.com` 下载模型
效果：本地 embedding 模型正常加载

**问题2：LLM 场景打标分布不均**

现象：首批 1,088 个单词中 86% 被标为"日常生活"，"影视剧"仅 2 个、"动漫"仅 1 个
根因：LLM prompt 允许返回"无"，且倾向于默认归类到日常生活
解决：修改 prompt 强制每个词至少选 1 个场景 + 新增关键词预匹配（对工作/商务/旅游/动漫/影视剧类词先行标记），二次运行后分布改善为日常 80% / 影视 7% / 动漫 4%

**问题3：前端 ImageSearch.vue 无路由**

现象：741 行代码没有任何路由引用，属于不可访问的死代码
解决：删除文件，功能已在 Search.vue 的图片搜索标签中实现
效果：减少 741 行无人维护的代码

---

> **最后更新:** 2026-07-14
