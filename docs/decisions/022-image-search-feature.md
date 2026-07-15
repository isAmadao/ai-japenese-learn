# 022 · 图片搜索单词功能

- **日期**: 2026-07-06
- **状态**: ✅ 已实现

## 功能概述

用户上传包含日语文字的图片，自动识别文字并搜索相关单词。支持 OCR（本地兜底）+ 大模型视觉识别（主要路径）双引擎，识别结果可跨页面持久化。

## 架构

```
用户上传图片
    │
    ├─→ EasyOCR (本地) ──→ 日语文字识别
    │    语言: ["ja", "en"]
    │    模型: craft_mlt_25k.pth (检测) + japanese_g2.pth (识别)
    │
    ├─→ LLM Vision (Qwen-VL) ──→ 日语文字 + 场景描述
    │    模型: qwen-vl-max → qwen-vl-plus (自动降级)
    │    API: DashScope OpenAI 兼容接口
    │
    ▼
    合并识别结果 ──→ 搜索单词库 (BM25 + 向量)
    │
    ├─→ CLIP 图库存储 (去重)
    │    Step 1: 字节哈希比对 (SHA256 → img_id)
    │    Step 2: 向量相似度 > 0.99
    │
    └─→ 返回结果 ──→ 前端持久化 (sessionStorage + URL)
```

## 后端实现

### 1. OCR 服务 (`backend/app/services/ocr_service.py`)

- **EasyOCR**: 本地 OCR 引擎，日语识别，模型从 GitHub 下载（国内需代理/镜像）
- **LLM Vision**: 通过 DashScope OpenAI 兼容接口调用 Qwen-VL 系列模型
- 两者通过 `ThreadPoolExecutor` 并行执行，结果合并去重

### 2. 图片搜索 API (`backend/app/api/image_search.py`)

```
POST /api/words/search-by-image
  Body: multipart/form-data
    - file: 图片文件 (JPEG/PNG/WebP, ≤10MB)
    - api_key: 用户提供的 LLM API Key (可选)
  Response:
    - results: 单词搜索结果
    - ocr_texts: 识别出的文字片段
    - scene: 场景描述
    - usable: 是否包含有意义的日语内容
    - saved_to_gallery: 是否已存入 CLIP 图库
    - processing_time_ms: 处理耗时
```

### 3. CLIP 图库去重 (`backend/app/api/image_search.py`)

```python
# Step 1: 字节哈希比对
content_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
img_id = int(content_hash, 16) % (2**31 - 1)
existing = milvus_client.get(CLIP_IMAGE_COLLECTION, img_id)

# Step 2: 向量相似度 > 0.99
img_vec = clip.encode_image_bytes(image_bytes)
similar = milvus_client.search(CLIP_IMAGE_COLLECTION, img_vec, top_k=3)
is_dup = any(hit.get("distance", 0) > 0.99 for hit in similar)
```

## 前端实现 (`frontend/src/views/Search.vue`)

### 持久化机制（关键）

```
saveImageSearch(data)  ← 搜索完成时调用
  ├─ 完整 ImageSearchResponse → sessionStorage
  └─ URL → ?img=1&q=识别文字

restoreImageSearch()    ← onMounted / switchMode('image') 时调用
  ├─ URL img=1 → 进入图片模式
  └─ sessionStorage → 恢复完整结果

clearImageSearch()      ← "换一张" 时调用
  ├─ 清除 sessionStorage
  └─ 移除 URL img 参数
```

### 模板条件（重点）

| 条件 | 控制 | 说明 |
|------|------|------|
| `!previewUrl && !restored` | 上传区域 | 恢复缓存时隐藏 |
| `previewUrl \|\| restored` | OCR 结果区 | 恢复缓存时也显示 |
| `v-if="previewUrl"` | 图片预览 | 恢复缓存时不显示（无 blob URL） |
| `v-if="restored"` | 新搜索按钮 | 恢复缓存时提供重新搜索入口 |

### 核心逻辑

```typescript
// query watcher 必须保留已有 URL 参数，否则 img=1 会被冲掉
watch(query, (newVal) => {
  router.replace({ query: { ...route.query, q: newVal || undefined } })
})

// 切 tab 不清缓存，只有"换一张"才清
function switchMode(m) {
  if (m === 'image') restoreImageSearch()  // 从 sessionStorage 恢复
  // 切到 text 时不调用 clearImageSearch()
}
```

## 遇到的问题

### 问题1：EasyOCR 模型下载被墙

**现象**: EasyOCR 首次使用需从 GitHub 下载 ~200MB 模型，国内网络连接失败
**根因**: GitHub Releases CDN 在国内被限制访问
**解决**: 
- 使用 `ghproxy.net` 代理 → 速度极慢（~0.3MB/s）
- 尝试清华镜像 `mirrors.tuna.tsinghua.edu.cn/github-release/` → 返回 403
- 最终放弃 EasyOCR 作为主要识别引擎，改用 LLM Vision + EasyOCR 仅作兜底
- HuggingFace 模型通过 `HF_ENDPOINT=https://hf-mirror.com` 环境变量解决

### 问题2：PaddleOCR 方案因依赖冲突放弃

**现象**: PaddlePaddle 3.3.1 有 OneDNN bug (`ConvertPirAttribute2RuntimeAttribute`)，降级到 2.6.x 又要求 protobuf 3.x 导致 pymilvus 不兼容。同时依赖链 `paddleocr → paddlex → modelscope → torch` 触发 torch DLL 错误
**解决**: 放弃 PaddleOCR，保持 EasyOCR + LLM Vision 架构

### 问题3：前端切页后结果丢失

**现象**: 图片搜索结果在导航到单词详情页后返回时消失
**根因分析**:
```
问题链:
1. saveImageSearch() 设置 URL ?img=1&q=文字
2. watch(query) 用 router.replace({ query: { q: newVal } }) 覆盖了整个 query
   → img=1 被冲掉
3. 切页回来时 onMounted 检测不到 img=1 → 不恢复
4. 即使 sessionStorage 有数据，也因为没有 img=1 而不触发 restoreImageSearch()
```
**解决**:
- `watch(query)` 改为 `router.replace({ query: { ...route.query, q: newVal } })` 保留 `img`
- 同时发现模板 `v-if="!previewUrl"` 隐藏了上传区域，导致恢复的 OCR 结果不可见
- 新增 `restored` 标志位解决

### 问题4：EasyOCR 语言参数错误

**现象**: `easyocr.Reader(["ja", "ch_sim", "en"])` 报错 `Chinese_sim is only compatible with English`
**根因**: EasyOCR 中 `ch_sim` 必须紧跟在 `en` 后面
**解决**: 改为 `["ja", "en"]`（项目只需要日语识别）

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/ocr_service.py` | OCR 服务：EasyOCR + LLM Vision |
| `backend/app/api/image_search.py` | 图片搜索 API 端点 |
| `backend/app/services/clip_service.py` | CLIP 编码（新增 encode_image_bytes） |
| `backend/app/services/image_service.py` | CLIP 图库存储（新增 from_bytes） |
| `backend/app/main.py` | 注册 image_search 路由 |
| `frontend/src/views/Search.vue` | 搜索页集成图片 tab |
| `frontend/src/api/index.ts` | 新增 searchWordsByImage API |
| `frontend/src/types/index.ts` | 新增 ImageSearchResponse 类型 |
| `frontend/src/router/index.ts` | 路由配置 |
| `frontend/vite.config.ts` | 代理配置 |
| `backend/requirements.txt` | 新增 easyocr, Pillow |

## 待办/优化

- [ ] EasyOCR 识别模型完整下载（当前只缓存了检测模型）
- [ ] 图片预览在 restored 模式下不可见（blob URL 限制）
- [ ] CLIP 图库的用户上传图片 URL 是虚拟的 `upload://` 格式，无法直接预览
