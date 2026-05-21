"""
LLM via Ollama sur l'hôte (pas dans Docker).
Ollama expose une API compatible OpenAI sur http://host.docker.internal:11434.
"""

import asyncio
import httpx
from .base import LLMProvider


class LocalOllamaLLMProvider(LLMProvider):
    """LLM via Ollama (hôte). Aucune donnée ne quitte la machine."""

    def __init__(self, base_url: str, model: str = "qwen2.5:7b", temperature: float = 0.1):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature

    async def chat(self, messages: list[dict], max_tokens: int = 512) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": self._temperature, "num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

    @property
    def provider_name(self) -> str:
        return "local_ollama"

    @property
    def model_name(self) -> str:
        return self._model
