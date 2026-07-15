"""Image Search API — upload image, search Japanese words via OCR + LLM Vision.

Flow:
  1. Accept image upload (multipart/form-data)
  2. Extract Japanese text via EasyOCR + LLM Vision (parallel)
  3. Search words by extracted text using existing search service
  4. If the image contains useful Japanese text, store CLIP embedding
     in the image gallery for future cross-modal retrieval
  5. Return search results + extracted text + gallery status
"""

import hashlib
import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.word import SearchResultItem
from app.services.ocr_service import extract_text_from_image
from app.services.word_service import word_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/words", tags=["image-search"])

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
}


@router.post("/search-by-image", response_model=dict)
async def search_words_by_image(
    file: UploadFile = File(..., description="待识别的图片（JPEG/PNG/WebP）"),
    api_key: str = Form("", description="用户提供的 LLM API Key（可选，用于大模型视觉识别）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传图片，识别其中的日语文字并搜索相关单词。

    流程：
    1. 同时使用 EasyOCR + 大模型视觉识别提取图片中的日语文字
    2. 用提取的文字搜索单词库
    3. 如果图片包含有用的日语内容，自动保存到 CLIP 图片图库
    4. 返回搜索结果 + 识别结果

    Returns:
        {
            "results": [...],      # 单词搜索结果
            "total": int,          # 结果总数
            "query": str,          # 搜索用的查询文本
            "ocr_texts": [str],    # OCR 提取的文字片段
            "scene": str,          # 大模型识别的场景描述
            "usable": bool,        # 图片是否包含有意义的日语内容
            "saved_to_gallery": bool,  # 是否已保存到图库
            "processing_time_ms": int,  # 处理耗时
        }
    """
    start = time.time()

    # ── 1. Validate upload ────────────────────────────────────
    if not file.file:
        raise HTTPException(status_code=400, detail="未收到图片文件")

    # Read image bytes
    image_bytes = await file.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="图片文件为空")

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"图片太大（最大 {MAX_IMAGE_SIZE // 1024 // 1024} MB）",
        )

    # Validate mime type (from content_type or magic bytes)
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {content_type}",
        )

    # ── 2. OCR + LLM Vision ──────────────────────────────────
    from app.core.config import settings
    llm_key = api_key or settings.LLM_API_KEY or None
    ocr_result = extract_text_from_image(image_bytes, llm_api_key=llm_key)

    query_text = ocr_result.get("full_text", "").strip()
    ocr_texts = ocr_result.get("texts", [])
    scene = ocr_result.get("scene", "")
    usable = ocr_result.get("usable", False)

    if not query_text:
        elapsed = int((time.time() - start) * 1000)
        return {
            "results": [],
            "total": 0,
            "query": "",
            "ocr_texts": [],
            "scene": scene or "未能从图片中识别出日语文字",
            "usable": False,
            "saved_to_gallery": False,
            "processing_time_ms": elapsed,
            "message": "未能从图片中识别出日语文字，请尝试上传包含日语文本的清晰图片",
        }

    # ── 3. Search words ──────────────────────────────────────
    search_result = word_service.search_words(db, q=query_text, top_k=30)

    # ── 4. Save to CLIP gallery (dedup: hash → vector similarity) ──
    saved_to_gallery = False
    if usable and ocr_texts:
        try:
            from app.services.clip_service import clip
            from app.services.image_service import store_image_clip_embedding_from_bytes
            from app.core.milvus_client import milvus_client

            # Generate a deterministic id from image content hash
            content_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
            img_id = int(content_hash, 16) % (2**31 - 1)

            is_dup = False

            # Step 1: Check byte-identical (same content hash → same id)
            try:
                existing = milvus_client.get(
                    milvus_client.CLIP_IMAGE_COLLECTION, img_id,
                )
                if existing:
                    logger.info("Byte-identical image already in CLIP gallery, skipping")
                    is_dup = True
            except Exception:
                pass  # get() may not be supported in fallback mode

            # Step 2: If not byte-identical, check CLIP vector similarity > 0.99
            if not is_dup:
                img_vec = clip.encode_image_bytes(image_bytes)
                if img_vec is not None:
                    similar = milvus_client.search(
                        milvus_client.CLIP_IMAGE_COLLECTION, img_vec, top_k=3,
                    )
                    is_dup = any(
                        hit.get("distance", 0) > 0.99
                        for hit in similar
                    )
                    if is_dup:
                        logger.info("Similar image already in CLIP gallery (similarity > 0.99), skipping")

            if not is_dup:
                saved_to_gallery = store_image_clip_embedding_from_bytes(
                    entity_type="user_upload",
                    entity_id=img_id,
                    image_bytes=image_bytes,
                    text_context=query_text[:500],
                )

            if saved_to_gallery:
                logger.info(
                    "Image saved to CLIP gallery (id=%d, text=%s)",
                    img_id, query_text[:50],
                )
        except Exception as e:
            logger.warning("Failed to save image to CLIP gallery: %s", e)
            saved_to_gallery = False

    elapsed = int((time.time() - start) * 1000)

    return {
        "results": [
            SearchResultItem(**r).model_dump()
            for r in search_result.get("results", [])
        ],
        "total": search_result.get("total", 0),
        "query": query_text,
        "ocr_texts": ocr_texts,
        "scene": scene,
        "usable": usable,
        "saved_to_gallery": saved_to_gallery,
        "processing_time_ms": elapsed,
    }
