import io
from .base import STTProvider


class GroqSTTProvider(STTProvider):
    """STT via l'API Groq (whisper-large-v3). Audio envoyé aux serveurs Groq."""

    def __init__(self, api_key: str, model: str = "whisper-large-v3-turbo"):
        from groq import Groq
        self._client = Groq(api_key=api_key)
        self._model = model

    async def transcribe(self, audio_bytes: bytes, language: str = "fr") -> str:
        import asyncio
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes, language)

    def _transcribe_sync(self, audio_bytes: bytes, language: str) -> str:
        result = self._client.audio.transcriptions.create(
            model=self._model,
            file=("audio.wav", io.BytesIO(audio_bytes), "audio/wav"),
            language=language,
        )
        return result.text.strip()

    @property
    def provider_name(self) -> str:
        return "groq"
