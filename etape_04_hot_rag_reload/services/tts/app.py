"""
Service TTS (Text-to-Speech)
─────────────────────────────
Expose un endpoint HTTP qui synthétise du texte en audio WAV
en utilisant piper-tts avec une voix française locale.

Endpoint : POST /synthesize
  - Entrée  : {"text": "Bonjour, comment puis-je vous aider ?"}
  - Sortie  : audio/wav (bytes)
"""

import io
import wave
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from piper.voice import PiperVoice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VOICE_MODEL_PATH = "/app/voices/fr_FR-siwis-medium.onnx"

voice: PiperVoice = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global voice
    logger.info(f"Chargement de la voix piper : {VOICE_MODEL_PATH}")
    voice = PiperVoice.load(VOICE_MODEL_PATH)
    logger.info("Voix piper prête.")
    yield


app = FastAPI(title="TTS Service (piper-tts)", lifespan=lifespan)


# ── Schéma de requête ──────────────────────────────────────────────────────────

class SynthesizeRequest(BaseModel):
    text: str
    speed: float = 1.0  # Vitesse de parole (0.5 = lent, 2.0 = rapide)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "voice": "fr_FR-siwis-medium"}


@app.post("/synthesize", response_class=Response)
async def synthesize(request: SynthesizeRequest):
    """
    Synthétise le texte fourni et retourne un fichier audio WAV.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")

    try:
        audio_buffer = io.BytesIO()

        with wave.open(audio_buffer, "wb") as wav_file:
            voice.synthesize(
                request.text,
                wav_file,
                length_scale=1.0 / request.speed,  # piper utilise length_scale
            )

        audio_buffer.seek(0)
        wav_bytes = audio_buffer.read()

        logger.info(f"Synthèse : {len(request.text)} caractères → {len(wav_bytes)} bytes WAV")

        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=response.wav"},
        )

    except Exception as exc:
        logger.error(f"Erreur TTS : {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
