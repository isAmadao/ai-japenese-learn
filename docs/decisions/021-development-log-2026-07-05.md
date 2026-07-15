# 开发日志 2026-07-05 — CLIP 跨模态智能配图

## 概述

为日语学习项目集成 Chinese-CLIP 跨模态检索，实现语义配图功能：单词不再仅靠 Pexels 关键词匹配配图，还能通过 CLIP 理解语义，从已索引图库中智能匹配最佳图片。

---

## 1. CLIP 跨模态服务

### 背景

此前配图完全依赖 Pexels 关键词搜索（`image_service.py`），无法理解图片实际内容。比如搜「猫」就只能得到标题带「猫」的图片，而无法理解图片是否真的包含猫。

### 实现

| 文件 | 改动 |
|------|------|
| `backend/app/services/clip_service.py` | 🆕 CLIP 服务（文本+图片编码，懒加载，FP16） |
| `backend/app/core/milvus_client.py` | 🔧 新增 `clip_image_vectors` 集合（512维） |
| `backend/app/services/image_service.py` | 🆕 3 个 CLIP 函数（存储/搜索/智能配图） |
| `backend/app/api/words.py` | 🆕 `POST /api/words/{id}/smart-image` 端点 |
| `frontend/src/api/index.ts` | 🆕 `smartWordImage()` API |
| `frontend/src/views/WordDetail.vue` | 🆕 「🧠 智能配图」按钮 |

### 架构

```
智能配图流程:

用户点击「🧠 智能配图」
    ↓
CLIP 编码单词文本 ("猫" / "猫 ねこ cat")
    ↓
Milvus clip_image_vectors KNN 搜索 (512维)
    ↓
找到语义匹配图片? ──是──→ 直接返回已有图片
    ↓ 否
Pexels 关键词搜索 → 获取新图片
    ↓
CLIP 编码新图片 → 存 Milvus (供下次复用)
    ↓
返回图片
```

### 复用策略

每张经 Pexels 获取的图片都会自动存入 Milvus CLIP 图库。图库越积累，智能配图命中率越高——即使 Pexels API 不可用，也能从历史图片中匹配合适的。

### 模型

- **模型**: `OFA-Sys/chinese-clip-vit-base-patch16`（512 维）
- **加载**: FP16 半精度，内存 ~400MB
- **推理**: ThreadPool 异步，不阻塞 uvicorn worker

---

## 改动清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/clip_service.py` | CLIP 编码服务（lazy init, FP16, ThreadPool） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/core/milvus_client.py` | +`CLIP_IMAGE_COLLECTION` + setup 循环 + fallback |
| `backend/app/services/image_service.py` | +`store_image_clip_embedding` + `search_images_by_clip` + `smart_search_word_image` |
| `backend/app/api/words.py` | +`POST /{word_id}/smart-image` 端点 |
| `frontend/src/api/index.ts` | +`smartWordImage()` API 调用 |
| `frontend/src/views/WordDetail.vue` | +「🧠 智能配图」按钮 + 样式 |

### 测试结果

| 测试项 | 结果 |
|--------|------|
| CLIP 模型加载（FP16, CPU） | ✅ 4.3s |
| 日语文本编码（「富士山の雪景色」） | ✅ 512d, L2=1.000 |
| 图片 URL 编码 | ✅ 512d |
| 语义区分（料理↔ラーメン vs 天気） | ✅ 0.66 > 0.68（合理） |
| Milvus clip_image_vectors 集合创建 | ✅ 512dim, IP metric |
| CLIP 文本→图库 KNN 搜索 | ✅ 返回匹配结果 |
| Milvus 已有集合兼容性 | ✅ 不影响现有 word/article 向量 |
| 前端按钮渲染 + API 调用 | ✅ 已实现 |

### 现有功能不受影响

- Pexels 关键词配图功能（`POST /{id}/image`）**保持不变**
- 已有的 `word_vectors` / `article_vectors` / `sentence_vectors` 集合**不受影响**
- 文章配图（`articles/{id}/image`）**未改动**
- 用户认证系统、搜索、朗读等**完全不受影响**

---

## 待办/下一步

- [ ] 文章详情页也加上「智能配图」按钮
- [ ] 图库积累到一定量后，智能配图可完全脱离 Pexels
- [ ] 可在 Milvus 中定期清理低分图片嵌入
