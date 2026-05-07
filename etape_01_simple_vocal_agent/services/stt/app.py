"""
Service STT (Speech-to-Text)
────────────────────────────
Expose un endpoint HTTP qui transcrit un fichier audio en texte.

Trois modes selon STT_PROVIDER :
  - "local"       (défaut) : faster-whisper, 100 % hors-ligne, rien ne quitte la machine
  - "huggingface"          : API HuggingFace Inference (nécessite HF_API_TOKEN)
  - "groq"                 : API Groq Whisper, gratuit et très rapide (nécessite GROQ_API_KEY)
                             ⚠ L'audio est envoyé aux serveurs Groq

Endpoint : POST /transcribe
  - Entrée  : fichier audio (multipart/form-data)
  - Sortie  : {"transcript": "...", "language": "fr", "duration_s": 3.2}
"""

import io
import os
import tempfile
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
STT_PROVIDER   = os.getenv("STT_PROVIDER", "local")   # "local" | "huggingface" | "groq"
HF_API_TOKEN   = os.getenv("HF_API_TOKEN") or os.getenv("HF_HUB_TOKEN") or os.getenv("HF_TOKEN", "")
HF_STT_MODEL   = os.getenv("HF_STT_MODEL", "openai/whisper-large-v3")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")

# Paramètres du mode local
MODEL_SIZE   = os.getenv("WHISPER_MODEL", "base")
MODEL_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
MODEL_DIR    = "/models"

model        = None   # WhisperModel (mode local)
_hf_client   = None   # InferenceClient (mode huggingface)
_groq_client = None   # Groq (mode groq)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, _hf_client, _groq_client
    if STT_PROVIDER == "local":
        from faster_whisper import WhisperModel
        logger.info(f"[STT] Mode local – chargement Whisper '{MODEL_SIZE}' sur {MODEL_DEVICE}...")
        model = WhisperModel(MODEL_SIZE, device=MODEL_DEVICE, download_root=MODEL_DIR)
        logger.info("[STT] Modèle Whisper prêt.")
    elif STT_PROVIDER == "groq":
        from groq import Groq
        if not GROQ_API_KEY:
            logger.warning("[STT] GROQ_API_KEY non défini – les appels Groq échoueront !")
        _groq_client = Groq(api_key=GROQ_API_KEY or None)
        logger.info(f"[STT] Mode Groq – modèle : {GROQ_STT_MODEL} (audio envoyé à Groq)")
    else:  # huggingface
        from huggingface_hub import InferenceClient
        if not HF_API_TOKEN:
            logger.warning("[STT] HF_API_TOKEN non défini – les appels HF échoueront !")
        _hf_client = InferenceClient(model=HF_STT_MODEL, token=HF_API_TOKEN or None)
        logger.info(f"[STT] Mode HuggingFace – modèle : {HF_STT_MODEL}")
    yield


app = FastAPI(title="STT Service", lifespan=lifespan)


# ── Transcription HuggingFace ──────────────────────────────────────────────────

def _transcribe_hf(audio_bytes: bytes) -> dict:
    result = _hf_client.automatic_speech_recognition(audio_bytes)
    text = result.text if hasattr(result, "text") else str(result)
    return {"transcript": text.strip(), "language": "fr", "language_probability": 1.0, "duration_s": 0.0}


# ── Transcription Groq ─────────────────────────────────────────────────────────

def _transcribe_groq(audio_bytes: bytes) -> dict:
    result = _groq_client.audio.transcriptions.create(
        model=GROQ_STT_MODEL,
        file=("audio.wav", io.BytesIO(audio_bytes), "audio/wav"),
        language="fr",
    )
    return {"transcript": result.text.strip(), "language": "fr", "language_probability": 1.0, "duration_s": 0.0}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    if STT_PROVIDER == "local":
        return {"status": "ok", "provider": "local", "model": MODEL_SIZE}
    if STT_PROVIDER == "groq":
        return {"status": "ok", "provider": "groq", "model": GROQ_STT_MODEL}
    return {"status": "ok", "provider": "huggingface", "model": HF_STT_MODEL}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(..., description="Fichier audio (WAV, MP3, OGG, etc.)"),
    language: str = Query(default="fr", description="Code langue ISO 639-1"),
):
    """Transcrit un fichier audio en texte (mode local, HuggingFace ou Groq selon STT_PROVIDER)."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fichier audio vide")

    # ── Mode HuggingFace ──────────────────────────────────────────────────────
    if STT_PROVIDER == "huggingface":
        try:
            result = _transcribe_hf(audio_bytes)
            logger.info(f"[HF STT] '{result['transcript'][:60]}'")
            return result
        except Exception as exc:
            logger.error(f"[HF STT] Erreur : {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Mode Groq ─────────────────────────────────────────────────────────────
    if STT_PROVIDER == "groq":
        try:
            result = _transcribe_groq(audio_bytes)
            logger.info(f"[Groq STT] '{result['transcript'][:60]}'")
            return result
        except Exception as exc:
            logger.error(f"[Groq STT] Erreur : {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Mode local (faster-whisper) ───────────────────────────────────────────
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
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        transcript = " ".join(seg.text.strip() for seg in segments)
        logger.info(
            f"[Local STT] lang={info.language} "
            f"proba={info.language_probability:.2f} durée={info.duration:.1f}s"
        )
        return {
            "transcript": transcript,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration_s": round(info.duration, 2),
        }
    except Exception as exc:
        logger.error(f"[Local STT] Erreur : {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        os.unlink(tmp_path)
