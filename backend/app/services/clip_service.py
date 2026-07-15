"""CLIP cross-modal service — Chinese-CLIP 文本⇄图片语义编码

为日语学习项目提供语义配图能力：
  - 文本编码: 日语单词/文章 → 512d 向量
  - 图片编码: 图片 URL → 512d 向量

使用方式:
    from app.services.clip_service import clip

    # 文本编码
    vec = clip.encode_text("富士山の雪景色")
    # 图片编码
    vec = clip.encode_image_url("https://example.com/fuji.jpg")

模型: OFA-Sys/chinese-clip-vit-base-patch16 (512 维)
首次调用时从 HuggingFace 加载（约 400MB 内存），之后本地缓存。
"""

import logging
import io
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

_CLIP_MODEL_NAME = "OFA-Sys/chinese-clip-vit-base-patch16"
_CLIP_DIMS = 512
_HTTP_TIMEOUT = 15
_MAX_IMAGE_SIZE = (1024, 1024)

# Thread pool for PyTorch inference (avoids blocking uvicorn workers)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clip")

# Lazy-loaded globals
_model = None
_processor = None


# ── Internal: lazy init ──────────────────────────────────────

def _lazy_init() -> bool:
    """Load the CLIP model on first call (lazy, FP16 for efficiency)."""
    global _model, _processor
    if _model is not None:
        return True

    import torch

    logger.info("🔄 Loading Chinese-CLIP model (%s) …", _CLIP_MODEL_NAME)
    logger.info("   (FP16, ~400MB RAM)")

    try:
        from transformers import ChineseCLIPModel, ChineseCLIPProcessor

        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Try local cache first (avoids network timeouts in China)
        try:
            _model = ChineseCLIPModel.from_pretrained(
                _CLIP_MODEL_NAME, local_files_only=True,
            ).to(device).half().eval()
            _processor = ChineseCLIPProcessor.from_pretrained(
                _CLIP_MODEL_NAME, local_files_only=True,
            )
            logger.info("✅ Chinese-CLIP loaded from cache (dims=%d, device=%s)",
                        _model.config.projection_dim, device)
        except OSError:
            logger.info("Model not in cache, downloading from HuggingFace …")
            _model = ChineseCLIPModel.from_pretrained(
                _CLIP_MODEL_NAME,
            ).to(device).half().eval()
            _processor = ChineseCLIPProcessor.from_pretrained(_CLIP_MODEL_NAME)
            logger.info("✅ Chinese-CLIP downloaded and loaded (dims=%d, device=%s)",
                        _model.config.projection_dim, device)

        return True

    except Exception as e:
        logger.error("❌ CLIP model loading failed: %s", e)
        return False


# ── Synchronous encoding (runs in thread pool) ───────────────

def _encode_text_sync(text: str) -> Optional[list[float]]:
    """Encode a single text string → 512d embedding (blocking, run in executor)."""
    if not _lazy_init():
        return None

    import torch
    try:
        with torch.no_grad():
            inputs = _processor(
                text=[text],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=77,
            )
            model_inputs = {
                "input_ids": inputs["input_ids"].to(_model.device),
                "attention_mask": inputs["attention_mask"].to(_model.device),
            }
            text_outputs = _model.text_model(**model_inputs)
            pooled = text_outputs.last_hidden_state[:, 0, :]
            emb = _model.text_projection(pooled)
            emb = emb / emb.norm(p=2, dim=-1, keepdim=True)
        return emb[0].cpu().tolist()
    except Exception as e:
        logger.warning("CLIP text encoding failed: %s", e)
        return None


def _encode_image_sync(image_data: bytes) -> Optional[list[float]]:
    """Encode raw image bytes → 512d embedding (blocking, run in executor)."""
    if not _lazy_init():
        return None

    import torch
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail(_MAX_IMAGE_SIZE, Image.LANCZOS)
        if img.mode != "RGB":
            img = img.convert("RGB")

        with torch.no_grad():
            inputs = _processor(images=img, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(_model.device)
            vision_outputs = _model.vision_model(pixel_values)
            pooled = vision_outputs.pooler_output
            if pooled is None:
                pooled = vision_outputs.last_hidden_state[:, 0, :]
            emb = _model.visual_projection(pooled)
            emb = emb / emb.norm(p=2, dim=-1, keepdim=True)
        return emb[0].cpu().tolist()
    except Exception as e:
        logger.warning("CLIP image encoding failed: %s", e)
        return None


# ── Public API ────────────────────────────────────────────────


class CLIPService:
    """CLIP text & image encoder for cross-modal retrieval.

    All encoding methods run PyTorch inference in a background thread
    so they never block the main uvicorn worker.
    """

    @property
    def dims(self) -> int:
        return _CLIP_DIMS

    @property
    def ready(self) -> bool:
        return _model is not None

    def encode_text(self, text: str) -> Optional[list[float]]:
        """Encode text → 512d L2-normalized embedding.

        Args:
            text: Japanese or Chinese text query.

        Returns:
            512-dim float list, or None on failure.
        """
        if not text or not text.strip():
            return None
        future = _executor.submit(_encode_text_sync, text.strip())
        return future.result()

    def encode_image_url(self, url: str) -> Optional[list[float]]:
        """Download & encode image from URL → 512d embedding.

        Args:
            url: Image URL.

        Returns:
            512-dim float list, or None on failure.
        """
        if not url:
            return None

        import httpx
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    ),
                })
                resp.raise_for_status()
                data = resp.content
        except Exception as e:
            logger.warning("CLIP: failed to fetch %s … %s", url[:50], e)
            return None

        if not data:
            return None

        return self.encode_image_bytes(data)

    def encode_image_bytes(self, image_bytes: bytes) -> Optional[list[float]]:
        """Encode raw image bytes → 512d embedding.

        Args:
            image_bytes: Raw image file content (JPEG, PNG, etc.).

        Returns:
            512-dim float list, or None on failure.
        """
        if not image_bytes:
            return None
        future = _executor.submit(_encode_image_sync, image_bytes)
        return future.result()


# ── Global singleton ──────────────────────────────────────────

clip = CLIPService()
