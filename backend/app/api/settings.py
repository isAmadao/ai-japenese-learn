"""Dictionary API — check status, stream upgrade, rollback."""

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from app.core.milvus_client import milvus_client
from app.services.japanese_util import (
    is_mecab_available,
    upgrade_to_mecab_stream,
    uninstall_mecab,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/dictionary")
def dictionary_status():
    """Check whether the MeCab dictionary (fugashi + unidic-lite) is installed."""
    mecab = is_mecab_available()
    return {
        "mecab_installed": mecab,
        "current": "mecab" if mecab else "pykakasi",
        "description": (
            "当前使用 pykakasi（轻量词典，覆盖常用汉字读音）"
            if not mecab
            else "已升级至 MeCab（完整日语词典，生僻汉字也可准确注音）"
        ),
    }


@router.get("/dictionary/upgrade")
def upgrade_dictionary_stream():
    """Stream pip install progress via SSE."""
    try:
        return StreamingResponse(
            (_format_sse(e) for e in upgrade_to_mecab_stream()),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.error(f"Dictionary upgrade failed: {e}")
        raise HTTPException(status_code=500, detail=f"词典升级失败: {str(e)[:100]}")


@router.post("/dictionary/rollback")
def rollback_dictionary():
    """Uninstall MeCab and revert to pykakasi."""
    try:
        result = uninstall_mecab()
        return result
    except Exception as e:
        logger.error(f"Dictionary rollback failed: {e}")
        raise HTTPException(status_code=500, detail=f"词典回退失败: {str(e)[:100]}")


@router.get("/debug/vectors")
def debug_vectors():
    """Debug: show vector storage state from the running process."""
    result = {
        "connected": milvus_client.connected,
        "using_fallback": milvus_client._using_fallback,
        "collections": dict(milvus_client.collections),
        "article_count": len(milvus_client._fallback_data.get("article_vectors", [])),
        "word_count": len(milvus_client._fallback_data.get("word_vectors", [])),
        "article_ids": [
            x.get("id") for x in milvus_client._fallback_data.get("article_vectors", [])
        ],
    }
    # If using real Milvus, try to query stored vectors
    if not milvus_client._using_fallback and milvus_client._client:
        try:
            milvus_client._client.load_collection("article_vectors")
            q = milvus_client._client.query("article_vectors", output_fields=["id", "title"], limit=10)
            result["milvus_articles"] = [
                {"id": item.get("id"), "title": item.get("title", "?")}
                for item in (q or [])
            ]
            result["milvus_count"] = len(q or [])
        except Exception as e:
            result["milvus_error"] = str(e)
    return result


def _format_sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
