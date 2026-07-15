"""OCR Service — Japanese text extraction from images.

Dual strategy:
  1. EasyOCR (primary) — local, offline, supports Japanese natively.
  2. LLM Vision (secondary) — Qwen-VL via DashScope, scene understanding + text.

Results are merged for better accuracy.  The LLM also provides scene context
that helps disambiguate homophones/glyphs.
"""

import base64
import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

logger = logging.getLogger(__name__)

_READER = None  # lazy-loaded EasyOCR reader
_OCR_LOCK = False


# ── Lazy init EasyOCR (heavy — ~200MB model download first time) ──


def _ensure_reader() -> bool:
    """Lazy-init EasyOCR reader for Japanese + Chinese + English."""
    global _READER, _OCR_LOCK
    if _READER is not None:
        return True
    if _OCR_LOCK:
        return False  # another thread is loading

    import threading
    _OCR_LOCK = True

    def _load():
        global _READER
        try:
            import easyocr
            logger.info("🔄 Loading EasyOCR (ja+ch_sim+en) …")
            _READER = easyocr.Reader(["ja", "en"], gpu=False)
            logger.info("✅ EasyOCR ready")
        except ImportError:
            logger.warning("easyocr not installed — OCR disabled")
        except Exception as e:
            logger.warning("EasyOCR init failed: %s", e)
        finally:
            global _OCR_LOCK
            _OCR_LOCK = False

    threading.Thread(target=_load, daemon=True).start()
    return False


def ocr_with_easyocr(image_bytes: bytes) -> list[dict]:
    """Extract Japanese text from image bytes using EasyOCR.

    Returns list of {text, confidence, bbox} or empty list.
    Returns empty list if EasyOCR models aren't cached yet (first-time download).
    """
    global _READER
    if _READER is None:
        # Reader not loaded yet — try quick sync init only if models already cached
        if not _ensure_reader():
            try:
                import easyocr
                if _READER is None:
                    # Only attempt sync init if detection model already exists
                    model_path = os.path.join(
                        os.path.dirname(easyocr.__file__), 'model', 'craft_mlt_25k.pth'
                    )
                    user_model = os.path.join(
                        os.path.expanduser('~'), '.EasyOCR', 'model', 'craft_mlt_25k.pth'
                    )
                    if os.path.exists(user_model) or os.path.exists(model_path):
                        _READER = easyocr.Reader(["ja", "en"], gpu=False)
            except ImportError:
                return []
            except Exception as e:
                logger.warning("EasyOCR sync init failed: %s", e)
                return []
        else:
            return []  # Still loading in background, skip for now

    if _READER is None:
        return []

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        # Convert to RGB if needed (EasyOCR expects RGB)
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        results = _READER.readtext(buf.getvalue())
        return [
            {
                "text": text.strip(),
                "confidence": round(conf, 3),
                "bbox": bbox,  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            }
            for bbox, text, conf in results
            if text.strip()
        ]
    except Exception as e:
        logger.warning("EasyOCR inference failed: %s", e)
        return []


# ── LLM Vision (Qwen-VL via DashScope) ──────────────────────────


def _try_vl_model(
    image_bytes: bytes,
    prompt: str,
    api_key: str,
    api_base: str,
    model: str,
) -> tuple:
    """Try a single VL model, return (response_text, error_code).

    Returns (text, None) on success, (None, error_type) on failure.
    error_type is 'auth' (401), 'timeout', 'model' (model not found), or 'other'.
    """
    import httpx
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64}"

    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 2048,
    }

    try:
        url = api_base.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code == 401:
                return None, "auth"
            if resp.status_code == 404:
                return None, "model"
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return (content.strip() if content else None, None)
    except httpx.TimeoutException:
        return None, "timeout"
    except Exception as e:
        logger.warning("VL model '%s' failed: %s", model, e)
        return None, "other"


def analyze_with_llm_vision(
    image_bytes: bytes,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Analyze image with LLM Vision: extract Japanese text + scene description.

    Tries multiple VL models in order (qwen-vl-max, qwen-vl-plus).
    If all VL models fail due to auth, logs a clear Chinese warning.

    Returns:
        {texts: [str], scene: str, raw_response: str}
    """
    from app.core.config import settings

    key = api_key or settings.LLM_API_KEY
    base = api_base or settings.LLM_API_BASE
    user_model = model

    if not key:
        logger.warning("No API key for LLM Vision")
        return {"texts": [], "scene": "", "raw_response": ""}

    # Prompt specifically for Japanese text extraction
    prompt = (
        "你是一位日语识别专家。请仔细查看图片，完成以下任务：\n\n"
        "1. 【提取日语文字】提取图片中所有可见的日语文字（汉字、平假名、片假名、日文标点），"
        "按出现顺序列出。注意不要遗漏图片中的标题、标签、说明文字中的日语内容。\n\n"
        "2. 【描述场景】用一句话描述图片中的场景或内容（中文）。\n\n"
        "3. 【判断可用性】这张图片是否包含有意义的日语学习内容？"
        "（单词、短语、句子、招牌、菜单等）回答「是」或「否」。\n\n"
        "请按以下格式回复：\n"
        "【提取的文字】\n<逐行列出的日语文字>\n\n"
        "【场景描述】\n<场景描述>\n\n"
        "【是否可用】\n<是/否>"
    )

    # Models to try, in order of preference
    models_to_try = [user_model] if user_model else ["qwen-vl-max", "qwen-vl-plus"]

    response = None
    last_error = None
    for vl_model in models_to_try:
        logger.info("Trying VL model: %s", vl_model)
        response, err = _try_vl_model(image_bytes, prompt, key, base, vl_model)
        if response:
            break
        last_error = err
        if err == "auth":
            logger.warning("❗ VL模型 %s 访问被拒绝（401），"
                           "请确认API Key是否开通了该模型权限", vl_model)
            continue  # Try next model
        if err == "model":
            logger.info("VL模型 %s 不可用，试试下一个", vl_model)
            continue

    if not response:
        if last_error == "auth":
            logger.warning("❗ 所有 VL 模型均返回 401。"
                           "请在 DashScope 控制台开通 qwen-vl-max 模型访问权限。"
                           "不影响 OCR 识别，只是无法获取场景描述。")
        return {"texts": [], "scene": "大模型视觉识别未能运行，只使用了 OCR 识别结果", "raw_response": ""}

    # Parse response
    texts = []
    scene = ""
    usable = False

    lines = response.split("\n")
    section = None
    for line in lines:
        line = line.strip()
        if line.startswith("【提取的文字】"):
            section = "texts"
            continue
        elif line.startswith("【场景描述】"):
            section = "scene"
            continue
        elif line.startswith("【是否可用】"):
            section = "usable"
            continue

        if section == "texts" and line:
            texts.append(line)
        elif section == "scene" and line:
            scene = line
        elif section == "usable" and line:
            usable = "是" in line or "可" in line

    return {
        "texts": [t for t in texts if t and not t.startswith("【")],
        "scene": scene,
        "usable": usable,
        "raw_response": response,
    }

# ── Combined OCR + LLM Vision ────────────────────────────────────


def extract_text_from_image(
    image_bytes: bytes,
    llm_api_key: Optional[str] = None,
    llm_api_base: Optional[str] = None,
    llm_model: Optional[str] = None,
    use_llm: bool = True,
) -> dict:
    """Extract Japanese text from image using OCR + LLM Vision.

    Runs EasyOCR and LLM Vision in parallel, then merges results.
    Returns:
        {
            "texts": [str],          # merged unique Japanese text fragments
            "full_text": str,        # concatenated text for search
            "scene": str,            # LLM scene description (if available)
            "usable": bool,          # whether image contains useful Japanese content
            "methods": {             # what each method produced
                "ocr": [str],
                "llm": [str],
            },
        }
    """
    ocr_result: list[str] = []
    llm_result: dict = {"texts": [], "scene": "", "usable": False}

    futures = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        # EasyOCR
        futures[pool.submit(ocr_with_easyocr, image_bytes)] = "ocr"
        # LLM Vision
        if use_llm:
            futures[
                pool.submit(
                    analyze_with_llm_vision,
                    image_bytes,
                    api_key=llm_api_key,
                    api_base=llm_api_base,
                    model=llm_model,
                )
            ] = "llm"

        for fut in as_completed(futures):
            tag = futures[fut]
            try:
                result = fut.result()
                if tag == "ocr":
                    ocr_result = [r["text"] for r in result if r.get("text")]
                elif tag == "llm":
                    llm_result = result if isinstance(result, dict) else {}
            except Exception as e:
                logger.warning("OCR task '%s' failed: %s", tag, e)

    # Merge: dedup by text, prefer longer/more specific
    seen = set()
    merged_texts = []

    for text in ocr_result:
        t = text.strip()
        if t and t not in seen:
            merged_texts.append(t)
            seen.add(t)

    for text in llm_result.get("texts", []):
        t = text.strip()
        if t and t not in seen:
            merged_texts.append(t)
            seen.add(t)

    # Build full text for search: use the longest combined string
    full_text = " ".join(merged_texts)
    if not full_text:
        # Fallback to scene description
        full_text = llm_result.get("scene", "")

    usable = bool(merged_texts) or llm_result.get("usable", False)

    return {
        "texts": merged_texts,
        "full_text": full_text,
        "scene": llm_result.get("scene", ""),
        "usable": usable,
        "methods": {
            "ocr": ocr_result,
            "llm": llm_result.get("texts", []),
        },
    }
