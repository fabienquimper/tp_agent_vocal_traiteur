"""
Service STT (Speech-to-Text)
────────────────────────────
Expose un endpoint HTTP qui transcrit un fichier audio en texte
en utilisant faster-whisper (implémentation optimisée de Whisper d'OpenAI).

Endpoint : POST /transcribe
  - Entrée  : fichier audio (multipart/form-data)
  - Sortie  : {"transcript": "...", "language": "fr", "duration_s": 3.2}
"""

import os
import tempfile
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Modèle chargé une seule fois au démarrage ─────────────────────────────────
MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
MODEL_DIR = "/models"

model: WhisperModel = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    logger.info(f"Chargement du modèle Whisper '{MODEL_SIZE}'...")
    model = WhisperModel(MODEL_SIZE, device="cpu", download_root=MODEL_DIR)
    logger.info("Modèle Whisper prêt.")
    yield


app = FastAPI(title="STT Service (Whisper)", lifespan=lifespan)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_SIZE}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(..., description="Fichier audio (WAV, MP3, OGG, etc.)"),
    language: str = Query(default="fr", description="Code langue ISO 639-1"),
):
    """
    Transcrit un fichier audio en texte.

    - language : "fr" pour forcer le français, None pour auto-détection
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fichier audio vide")

    # Écriture dans un fichier temporaire (faster-whisper nécessite un chemin)
    suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        lang_arg = language if language else None
        segments, info = model.transcribe(
            tmp_path,
            language=lang_arg,
            beam_size=5,
            vad_filter=True,          # Supprime les silences
            vad_parameters={"min_silence_duration_ms": 500},
        )

        # Les segments sont un générateur – on les consomme tous
        transcript = " ".join(seg.text.strip() for seg in segments)

        logger.info(
            f"Transcription : lang={info.language} "
            f"proba={info.language_probability:.2f} "
            f"durée={info.duration:.1f}s"
        )

        return {
            "transcript": transcript,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration_s": round(info.duration, 2),
        }

    except Exception as exc:
        logger.error(f"Erreur de transcription : {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        os.unlink(tmp_path)
