"""
Service TTS (Text-to-Speech)
─────────────────────────────
Expose un endpoint HTTP qui synthétise du texte en audio WAV.

Deux modes selon TTS_PROVIDER :
  - "local"       (défaut) : piper-tts, voix française locale, 100 % hors-ligne
  - "huggingface"          : API HuggingFace Inference (nécessite HF_API_TOKEN)

Endpoint : POST /synthesize
  - Entrée  : {"text": "Bonjour, comment puis-je vous aider ?"}
  - Sortie  : audio/wav (bytes)
"""

import io
import os
import wave
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
TTS_PROVIDER  = os.getenv("TTS_PROVIDER", "local")          # "local" | "huggingface"
# Accepte HF_API_TOKEN, HF_HUB_TOKEN ou HF_TOKEN (tous équivalents)
HF_API_TOKEN  = os.getenv("HF_API_TOKEN") or os.getenv("HF_HUB_TOKEN") or os.getenv("HF_TOKEN", "")
HF_TTS_MODEL  = os.getenv("HF_TTS_MODEL", "hexgrad/Kokoro-82M")

VOICE_MODEL_PATH = "/app/voices/fr_FR-siwis-medium.onnx"

voice      = None   # PiperVoice (mode local)
_hf_client = None   # InferenceClient (mode huggingface)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global voice, _hf_client
    if TTS_PROVIDER == "local":
        from piper.voice import PiperVoice
        logger.info(f"[TTS] Mode local – chargement de la voix piper : {VOICE_MODEL_PATH}")
        voice = PiperVoice.load(VOICE_MODEL_PATH)
        logger.info("[TTS] Voix piper prête.")
    else:
        from huggingface_hub import InferenceClient
        if not HF_API_TOKEN:
            logger.warning("[TTS] HF_API_TOKEN non défini – les appels HF échoueront !")
        _hf_client = InferenceClient(
            model=HF_TTS_MODEL,
            token=HF_API_TOKEN or None,
        )
        logger.info(f"[TTS] Mode HuggingFace – modèle : {HF_TTS_MODEL}")
    yield


app = FastAPI(title="TTS Service", lifespan=lifespan)


# ── Schéma de requête ──────────────────────────────────────────────────────────

class SynthesizeRequest(BaseModel):
    text: str
    speed: float = 1.0


# ── Synthèse via HuggingFace InferenceClient ──────────────────────────────────

def _synthesize_hf(text: str) -> bytes:
    """Synthétise le texte via HuggingFace InferenceClient (gère le routing HF automatiquement)."""
    audio = _hf_client.text_to_speech(text)
    return bytes(audio) if not isinstance(audio, bytes) else audio


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    if TTS_PROVIDER == "local":
        return {"status": "ok", "provider": "local", "voice": "fr_FR-siwis-medium"}
    return {"status": "ok", "provider": "huggingface", "model": HF_TTS_MODEL}


@app.post("/synthesize", response_class=Response)
async def synthesize(request: SynthesizeRequest):
    """Synthétise le texte en audio (mode local ou HuggingFace selon TTS_PROVIDER)."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")

    # ── Mode HuggingFace ──────────────────────────────────────────────────────
    if TTS_PROVIDER == "huggingface":
        try:
            audio_bytes = _synthesize_hf(request.text)
            logger.info(f"[HF TTS] {len(request.text)} caractères → {len(audio_bytes)} bytes")
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": "inline; filename=response.wav"},
            )
        except Exception as exc:
            logger.error(f"[HF TTS] Erreur : {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Mode local (piper-tts) ────────────────────────────────────────────────
    try:
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wav_file:
            voice.synthesize(
                request.text,
                wav_file,
                length_scale=1.0 / request.speed,
            )
        audio_buffer.seek(0)
        wav_bytes = audio_buffer.read()
        logger.info(f"[Local TTS] {len(request.text)} caractères → {len(wav_bytes)} bytes WAV")
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=response.wav"},
        )
    except Exception as exc:
        logger.error(f"[Local TTS] Erreur : {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
