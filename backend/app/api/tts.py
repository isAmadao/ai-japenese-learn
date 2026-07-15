"""TTS (Text-to-Speech) — server-side Japanese pronunciation fallback.

Uses Microsoft Edge TTS (free, no API key, works from China).
Frontend calls this when the browser's Web Speech API fails
(common on Android phones without Japanese TTS voice pack).
"""

import logging
import os
from typing import Optional

import edge_tts
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["tts"])

# ── Configuration ───────────────────────────────────────────

# Japanese voice options:
#   ja-JP-NanamiNeural  — female, natural (recommended)
#   ja-JP-KeitaNeural   — male
#   ja-JP-AoiNeural     — female, younger
TTS_VOICE = os.getenv("TTS_VOICE", "ja-JP-NanamiNeural")

# ── Models ───────────────────────────────────────────────────

class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500, description="Japanese text to speak")


# ── Endpoints ───────────────────────────────────────────────

@router.head("/ping")
def tts_ping():
    """Lightweight probe — 204 = TTS available."""
    return  # 204 No Content


@router.post("")
async def text_to_speech(req: TtsRequest) -> Response:
    """Convert Japanese text to speech and return WAV audio."""
    audio_bytes = await _synthesize(req.text)
    return Response(content=audio_bytes, media_type="audio/mpeg")


# ── Provider: Microsoft Edge TTS ────────────────────────────

async def _synthesize(text: str, voice: str = TTS_VOICE) -> bytes:
    """Call Microsoft Edge TTS and return audio bytes."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        audio_chunks: list[bytes] = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            raise HTTPException(status_code=502, detail="TTS returned no audio data")

        logger.info(f"TTS: synthesized {sum(len(c) for c in audio_chunks)} bytes (voice={voice})")
        return b"".join(audio_chunks)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise HTTPException(status_code=502, detail=f"TTS error: {str(e)[:100]}")
