"""
STT via LM Studio (si LM Studio supporte Whisper via son API OpenAI-compatible).
LM Studio expose : POST http://localhost:1234/v1/audio/transcriptions
"""

import io
import httpx
from .base import STTProvider


class LocalLMSSTTProvider(STTProvider):
    """STT via LM Studio (OpenAI-compatible API)."""

    def __init__(self, base_url: str = "http://host.docker.internal:1234", model: str = "whisper"):
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def transcribe(self, audio_bytes: bytes, language: str = "fr") -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/v1/audio/transcriptions",
                files={"file": ("audio.wav", io.BytesIO(audio_bytes), "audio/wav")},
                data={"model": self._model, "language": language},
            )
            resp.raise_for_status()
            return resp.json().get("text", "").strip()

    @property
    def provider_name(self) -> str:
        return "local_lms"
