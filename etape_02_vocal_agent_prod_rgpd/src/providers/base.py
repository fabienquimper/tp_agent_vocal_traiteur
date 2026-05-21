"""
Interfaces abstraites pour les providers STT et LLM.

Une interface = un contrat. Aucun if-else sur le provider
ne doit apparaître en dehors de factory.py.
"""

from abc import ABC, abstractmethod


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str = "fr") -> str:
        """Transcrit un audio en texte. Retourne le texte transcrit."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifiant lisible du provider, pour les logs."""
        ...


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], max_tokens: int = 512) -> str:
        """
        Envoie une liste de messages et retourne la réponse texte.
        Format messages : [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    def last_usage(self) -> dict:
        """
        Retourne l'usage tokens du dernier appel :
        {"input_tokens": int, "output_tokens": int}
        Les providers qui ne supportent pas les token counts retournent {0, 0}.
        """
        return {"input_tokens": 0, "output_tokens": 0}
