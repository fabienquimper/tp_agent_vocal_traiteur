"""
LLM via LM Studio (API OpenAI-compatible).
LM Studio expose : http://localhost:1234/v1
"""

import httpx
from .base import LLMProvider


class LocalLMSLLMProvider(LLMProvider):
    """LLM via LM Studio (OpenAI-compatible)."""

    def __init__(self, base_url: str = "http://host.docker.internal:1234", model: str = "local-model", temperature: float = 0.1):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature

    async def chat(self, messages: list[dict], max_tokens: int = 512) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": self._temperature,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    @property
    def provider_name(self) -> str:
        return "local_lms"

    @property
    def model_name(self) -> str:
        return self._model
