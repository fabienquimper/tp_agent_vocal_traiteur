import asyncio
from .base import LLMProvider


class GroqLLMProvider(LLMProvider):
    """LLM via l'API Groq."""

    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant", temperature: float = 0.1):
        from groq import Groq
        self._client = Groq(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._last_usage = {"input_tokens": 0, "output_tokens": 0}

    async def chat(self, messages: list[dict], max_tokens: int = 512) -> str:
        return await asyncio.to_thread(self._chat_sync, messages, max_tokens)

    def _chat_sync(self, messages: list[dict], max_tokens: int) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=self._temperature,
        )
        if resp.usage:
            self._last_usage = {
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
            }
        return resp.choices[0].message.content.strip()

    @property
    def last_usage(self) -> dict:
        return self._last_usage

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model
