import asyncio
from .base import LLMProvider


class MistralLLMProvider(LLMProvider):
    """LLM via l'API Mistral (La Plateforme)."""

    def __init__(self, api_key: str, model: str = "mistral-small-latest", temperature: float = 0.1):
        from mistralai import Mistral
        self._client = Mistral(api_key=api_key)
        self._model = model
        self._temperature = temperature

    async def chat(self, messages: list[dict], max_tokens: int = 512) -> str:
        return await asyncio.to_thread(self._chat_sync, messages, max_tokens)

    def _chat_sync(self, messages: list[dict], max_tokens: int) -> str:
        resp = self._client.chat.complete(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=self._temperature,
        )
        return resp.choices[0].message.content.strip()

    @property
    def provider_name(self) -> str:
        return "mistral"

    @property
    def model_name(self) -> str:
        return self._model
