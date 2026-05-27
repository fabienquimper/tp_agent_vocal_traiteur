"""
STT local via faster-whisper (pas Ollama — Ollama ne supporte pas encore Whisper).
Le nom "local_ollama" reflète le mode "100 % local" par opposition aux providers cloud.
Le modèle Whisper tourne dans le conteneur agent, aucune donnée audio ne quitte la machine.
"""

import os
import tempfile
import asyncio
from .base import STTProvider

_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
_MODEL_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
_MODEL_DIR = "/models"


class LocalOllamaSTTProvider(STTProvider):
    """STT local via faster-whisper. 100 % hors-ligne."""

    def __init__(self, model_size: str = _MODEL_SIZE, device: str = _MODEL_DEVICE):
        from faster_whisper import WhisperModel
        self._model = WhisperModel(model_size, device=device, download_root=_MODEL_DIR)
        self._model_size = model_size

    async def transcribe(self, audio_bytes: bytes, language: str = "fr") -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes, language)

    def _transcribe_sync(self, audio_bytes: bytes, language: str) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            segments, _ = self._model.transcribe(
                tmp_path,
                language=language or None,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            return " ".join(seg.text.strip() for seg in segments)
        finally:
            os.unlink(tmp_path)

    @property
    def provider_name(self) -> str:
        return "local_ollama"
